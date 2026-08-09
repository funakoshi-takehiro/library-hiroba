"""ui.form / ui.field の検証。

環境ごとに経路が変わるため、ipywidgets と IPython を偽物に差し替えて
それぞれの経路が意図どおり選ばれることまで確かめる。
"""

from __future__ import annotations

import asyncio
import sys
import types

import pytest
from sanitize_check import check_html

from library_hiroba import ui


def fake_ipywidgets(monkeypatch):
    """ipywidgets の代役を入れ、その module を返す。"""

    class FakeWidget:
        def __init__(self, **kwargs):
            self.value = kwargs.get("value", "")
            self.kwargs = kwargs
            self.fn = None

        def on_click(self, fn):
            self.fn = fn

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake = types.ModuleType("ipywidgets")
    for name in ("Text", "Textarea", "FloatText", "Dropdown", "Button", "Output", "HTML"):
        setattr(fake, name, FakeWidget)
    fake.VBox = lambda children: {"vbox": list(children)}
    monkeypatch.setitem(sys.modules, "ipywidgets", fake)
    return fake


def make_form(**kwargs):
    def handler(question):
        return ui.card("答え", question)

    return ui.form(handler, ui.field("question", label="質問"), **kwargs)


# --- 組み立てと検証 ---------------------------------------------------------


def test_field_validation():
    with pytest.raises(ValueError):
        ui.field("2つめ")  # 変数名にできない
    with pytest.raises(ValueError):
        ui.field("a", kind="slider")  # 未対応の種類
    with pytest.raises(ValueError):
        ui.field("a", kind="choice")  # choices が無い


def test_form_validation():
    with pytest.raises(ValueError):
        ui.form(lambda: None)  # 入力欄が無い
    with pytest.raises(ValueError):
        ui.form("関数ではない", "a")
    with pytest.raises(ValueError):
        ui.form(lambda a: a, "a", "a")  # name の重複


def test_string_shorthand_becomes_text_field():
    f = ui.form(lambda question: ui.card(question), "question")
    assert [x.name for x in f.fields] == ["question"]
    assert f.fields[0].kind == "text"


def test_submit_calls_handler():
    f = make_form()
    assert isinstance(f.submit(question="スマホは？"), ui.Widget)
    with pytest.raises(ValueError):
        f.submit()  # 入力値が足りない


# --- 出力の HTML ------------------------------------------------------------


def test_markup_carries_the_handshake_attributes():
    """PyHiroba 本体が値を受け渡すために見る目印が揃っていること。"""
    f = make_form(title="質問してみよう")
    html = f._repr_html_()
    assert f'data-hui-form="{f.form_id}"' in html
    assert 'data-hui-field="question"' in html
    assert f'data-hui-submit="{f.form_id}"' in html
    assert f'data-hui-output="{f.form_id}"' in html
    assert check_html(html) == []


def test_form_ids_are_unique():
    assert make_form().form_id != make_form().form_id


@pytest.mark.parametrize(
    ("kind", "kwargs", "expected"),
    [
        ("text", {}, "<input "),
        ("number", {}, 'type="number"'),
        ("multiline", {}, "<textarea "),
        ("choice", {"choices": ["小", "大"]}, "<select "),
    ],
)
def test_each_kind_renders_its_control(kind, kwargs, expected):
    html = ui.form(lambda a: ui.card(a), ui.field("a", kind=kind, **kwargs))._repr_html_()
    assert expected in html
    assert check_html(html) == []


def test_user_text_is_escaped():
    evil = '"><script>alert(1)</script>'
    html = ui.form(
        lambda a: ui.card(a),
        ui.field("a", label=evil, placeholder=evil, default=evil),
        submit_label=evil,
        title=evil,
    )._repr_html_()
    assert check_html(html) == []
    assert "<script" not in html.lower()


# --- 経路の選択 -------------------------------------------------------------


class _FakeDisplay:
    """IPython.display の代役。display() に渡された物を記録する。"""

    def __init__(self):
        self.displayed = []

    def module(self):
        mod = types.ModuleType("IPython.display")
        mod.display = self.displayed.append
        mod.clear_output = lambda **k: None
        return mod


@pytest.fixture
def fake_ipython(monkeypatch):
    recorder = _FakeDisplay()
    ipython = types.ModuleType("IPython")
    monkeypatch.setitem(sys.modules, "IPython", ipython)
    monkeypatch.setitem(sys.modules, "IPython.display", recorder.module())
    return recorder


def test_falls_back_to_input_without_ipywidgets(fake_ipython, monkeypatch):
    monkeypatch.setitem(sys.modules, "ipywidgets", None)  # import すると ImportError
    monkeypatch.setattr("builtins.input", lambda prompt="": "入力した質問")
    make_form()._ipython_display_()
    assert len(fake_ipython.displayed) == 1
    assert "入力した質問" in fake_ipython.displayed[0]._repr_html_()


def test_uses_ipywidgets_when_available(fake_ipython, monkeypatch):
    fake_ipywidgets(monkeypatch)
    make_form()._ipython_display_()
    assert fake_ipython.displayed and "vbox" in fake_ipython.displayed[0]
    # ボタンが押されたときに handler が呼ばれ、結果が表示されること
    button = fake_ipython.displayed[0]["vbox"][1]
    button.fn(None)
    assert any(isinstance(x, ui.Widget) for x in fake_ipython.displayed)


def test_repr_html_is_used_when_ipython_is_absent():
    """PyHiroba には IPython が無いので、静的な HTML の経路が使われる。"""
    if "IPython" in sys.modules:
        pytest.skip("IPython のある環境では対象外")
    html = make_form()._repr_html_()
    assert html.startswith('<div class="hui">')
    assert "hui-submit" in html


# --- PyHiroba 本体からの呼び出し口 -------------------------------------------


def test_form_is_registered_only_after_it_is_displayed():
    f = make_form()
    assert ui.get_form(f.form_id) is None
    f._repr_html_()
    assert ui.get_form(f.form_id) is f


def test_host_can_submit_through_the_registry():
    """PyHiroba 本体が行う手順（ID で引いて値を渡す）をそのまま再現する。"""
    f = make_form()
    f._repr_html_()
    result = ui.get_form(f.form_id).submit(question="スマホは持っていっていい？")
    assert "スマホは持っていっていい？" in result._repr_html_()


def test_unknown_form_id_returns_none():
    assert ui.get_form("hui-form-does-not-exist") is None


def test_registry_does_not_grow_without_bound():
    from library_hiroba import _forms

    for _ in range(_forms._REGISTRY_LIMIT + 20):
        make_form()._repr_html_()
    assert len(_forms._REGISTRY) <= _forms._REGISTRY_LIMIT


def test_clear_on_submit_empties_text_fields(fake_ipython, monkeypatch):
    fake_ipywidgets(monkeypatch)
    ui.form(lambda question: ui.card(question), "question", clear_on_submit=True)._ipython_display_()
    children = fake_ipython.displayed[0]["vbox"]
    text_box, button = children[0], children[1]

    text_box.value = "スマホは？"
    button.fn(None)
    assert text_box.value == ""


def test_values_are_kept_when_clear_on_submit_is_off(fake_ipython, monkeypatch):
    fake_ipywidgets(monkeypatch)
    ui.form(lambda question: ui.card(question), "question")._ipython_display_()
    children = fake_ipython.displayed[0]["vbox"]
    text_box, button = children[0], children[1]

    text_box.value = "そのまま残る"
    button.fn(None)
    assert text_box.value == "そのまま残る"


# --- async な handler（ai.ask を呼ぶ場合） -----------------------------------


def make_async_form(**kwargs):
    async def handler(question):
        await asyncio.sleep(0)  # ai.ask() のように、待つ処理が入る
        return ui.card("答え", question)

    return ui.form(handler, ui.field("question", label="質問"), **kwargs)


def test_async_handler_is_awaited_on_the_input_path(fake_ipython, monkeypatch):
    monkeypatch.setitem(sys.modules, "ipywidgets", None)
    monkeypatch.setattr("builtins.input", lambda prompt="": "スマホは持っていっていい？")
    make_async_form()._ipython_display_()
    # コルーチンのままではなく、待った結果が表示される
    assert len(fake_ipython.displayed) == 1
    shown = fake_ipython.displayed[0]
    assert isinstance(shown, ui.Widget)
    assert "スマホは持っていっていい？" in shown._repr_html_()


def test_async_handler_is_awaited_on_the_ipywidgets_path(fake_ipython, monkeypatch):
    fake_ipywidgets(monkeypatch)
    make_async_form()._ipython_display_()
    children = fake_ipython.displayed[0]["vbox"]
    text_box, button = children[0], children[1]
    text_box.value = "2の8乗は？"
    button.fn(None)
    widgets_shown = [x for x in fake_ipython.displayed if isinstance(x, ui.Widget)]
    assert widgets_shown and "2の8乗は？" in widgets_shown[-1]._repr_html_()


def test_async_handler_is_scheduled_when_a_loop_is_running(fake_ipython):
    """ノートブックの中（ループが回っている）では、ループに載せて後から表示する。"""
    from library_hiroba._forms import display_result

    async def handler():
        await asyncio.sleep(0)
        return ui.card("答え", "あとから届く")

    async def main():
        display_result(handler())
        assert fake_ipython.displayed == []  # この時点ではまだ待っている
        await asyncio.sleep(0.05)  # ループに順番をゆずる
        assert len(fake_ipython.displayed) == 1
        assert "あとから届く" in fake_ipython.displayed[0]._repr_html_()

    asyncio.run(main())


def test_sync_handler_is_still_displayed_directly(fake_ipython):
    from library_hiroba._forms import display_result

    card = ui.card("答え", "すぐ出る")
    display_result(card)
    assert fake_ipython.displayed == [card]


def test_submit_returns_the_awaitable_for_the_host():
    """PyHiroba 本体は、返り値が待つものなら await してから表示する。"""
    f = make_async_form()
    f._repr_html_()
    result = ui.get_form(f.form_id).submit(question="質問")
    assert asyncio.iscoroutine(result)
    assert "質問" in asyncio.run(result)._repr_html_()


# --- 監査で見つかった不具合の再発防止 ---------------------------------------


def test_number_field_returns_a_number_on_the_input_path(monkeypatch):
    """ipywidgets 経路は float を返すので、input() 経路も揃える（B4）。"""
    monkeypatch.setattr("builtins.input", lambda prompt="": "42")
    value = ui.field("a", kind="number").ask_via_input()
    assert isinstance(value, float) and value == 42.0


def test_number_field_asks_again_then_gives_up(monkeypatch, capsys):
    answers = iter(["いち", "に", "3"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert ui.field("a", kind="number").ask_via_input() == 3.0

    answers = iter(["a", "b", "c"])
    with pytest.raises(ValueError, match="could not convert"):
        ui.field("a", kind="number").ask_via_input()


def test_choice_field_rejects_values_outside_the_choices(monkeypatch):
    answers = iter(["特大", "大"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    field = ui.field("size", kind="choice", choices=["小", "大"])
    assert field.ask_via_input() == "大"


def test_choice_default_matches_across_paths():
    """default 未指定なら、両経路とも最初の選択肢から始まる（B5）。"""
    field = ui.field("size", kind="choice", choices=["小", "大"])
    assert field.default == "小"
    assert 'value="小" selected' in field.control_html()


# --- 監査で見つかった取りこぼし -------------------------------------------


def test_multiline_default_keeps_its_line_breaks():
    """textarea の中身はタグとして解釈されない。

    改行を <br> にすると「<br>」という文字がそのまま見えてしまう。
    """
    rendered = ui.field("memo", kind="multiline", default="1行目\n2行目").fragment()
    assert "<br>" not in rendered
    assert "1行目\n2行目" in rendered


def test_multiline_default_is_still_escaped():
    rendered = ui.field("memo", kind="multiline", default="</textarea><script>x</script>").fragment()
    assert "<script" not in rendered
    assert "&lt;/textarea&gt;" in rendered


@pytest.mark.parametrize("name", ["class", "for", "if", "lambda", "None", "import"])
def test_python_keywords_are_rejected_as_field_names(name):
    """予約語は handler の引数にできない。

    以前は field() を通り、ボタンを押した時点で初めて
    「handler() got an unexpected keyword argument 'class'」になっていた。
    書いた本人には原因が分からないので、作る時点で止める。
    """
    with pytest.raises(ValueError, match="予約語"):
        ui.field(name)


@pytest.mark.parametrize("name", ["class_", "組", "answer", "x2"])
def test_ordinary_names_still_work(name):
    assert ui.field(name).name == name
