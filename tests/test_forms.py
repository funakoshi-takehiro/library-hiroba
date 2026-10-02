"""ui.form / ui.field の検証。

環境ごとに経路が変わるため、ipywidgets と IPython を偽物に差し替えて
それぞれの経路が意図どおり選ばれることまで確かめる。
"""

from __future__ import annotations

import asyncio
import re
import sys
import types

import pytest
from conftest import require_ipywidgets, without_ipython
from sanitize_check import check_html

from library_hiroba import ui


def fake_ipywidgets(monkeypatch):
    """ipywidgets の代役を入れ、その module を返す。"""

    class FakeWidget:
        # 本物の HTML(...) は値を位置引数でも受け取る。Output は outputs を持ち、
        # add_class で CSS クラスが付く。どれも実装側が使うので代役にも持たせる
        def __init__(self, value="", **kwargs):
            self.value = kwargs.get("value", value)
            self.kwargs = kwargs
            self.fn = None
            self.outputs = ()
            self.classes = []

        def add_class(self, name):
            self.classes.append(name)
            return self

        def on_click(self, fn):
            self.fn = fn

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake = types.ModuleType("ipywidgets")
    for name in ("Text", "Textarea", "FloatText", "Dropdown", "Button", "Output", "HTML"):
        setattr(fake, name, FakeWidget)

    class FakeBox(dict):
        def __init__(self, children):
            super().__init__(vbox=list(children))
            self.classes = []

        def add_class(self, name):
            self.classes.append(name)
            return self

    fake.VBox = FakeBox
    monkeypatch.setitem(sys.modules, "ipywidgets", fake)
    return fake


def widgets_of(fake_ipython):
    """表示された VBox から、入力欄・送信ボタン・出力欄を役割で取り出す。

    位置で取ると、<style> や見出しを足したときに崩れる。
    """
    children = fake_ipython.displayed[0]["vbox"]
    button = next(c for c in children if getattr(c, "fn", None) is not None)
    # description はどの種類の入力欄にも付く。<style>・見出し・出力欄には無い
    control = next(
        c
        for c in children
        if c is not button and hasattr(c, "kwargs") and "description" in c.kwargs
    )
    return control, button


def output_html(fake_ipython):
    """出力欄（VBox の最後）に、いま入っている HTML。空なら ""。"""
    output = fake_ipython.displayed[0]["vbox"][-1]
    if not output.outputs:
        return ""
    return "".join(
        entry.get("data", {}).get("text/html", "") + entry.get("text", "")
        for entry in output.outputs
    )


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
    """IPython.display の代役。display() に渡された物を記録する。

    本物と同じく ``display_id=True`` を受け取り、差し替え用の取っ手を返す
    （「考え中」から答えへの差し替えがこれを使う）。
    """

    def __init__(self):
        self.displayed = []

    def _display(self, obj, display_id=None):
        self.displayed.append(obj)
        return self

    def update(self, obj):
        """取っ手として使われたとき。前の表示を差し替える。"""
        self.displayed.append(obj)

    def module(self):
        mod = types.ModuleType("IPython.display")
        mod.display = self._display
        mod.clear_output = lambda **k: None
        return mod

    @property
    def widgets_shown(self):
        """表示されたもののうち、部品だけ（考え中を除く）。"""
        return [
            x
            for x in self.displayed
            if isinstance(x, ui.Widget) and "hui-thinking" not in x._repr_html_()
        ]


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
    # ボタンが押されたときに handler が呼ばれ、結果が出力欄に入ること
    _text_box, button = widgets_of(fake_ipython)
    button.fn(None)
    assert "hui-card" in output_html(fake_ipython)


def test_repr_html_is_used_when_ipython_is_absent(monkeypatch):
    """PyHiroba には IPython が無いので、静的な HTML の経路が使われる。"""
    without_ipython(monkeypatch)
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
    text_box, button = widgets_of(fake_ipython)

    text_box.value = "スマホは？"
    button.fn(None)
    assert text_box.value == ""


def test_values_are_kept_when_clear_on_submit_is_off(fake_ipython, monkeypatch):
    fake_ipywidgets(monkeypatch)
    ui.form(lambda question: ui.card(question), "question")._ipython_display_()
    text_box, button = widgets_of(fake_ipython)

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
    # 待つあいだは「考え中」、そのあと結果に差し替わる
    # （コルーチンがそのまま出るのではない）
    assert [type(x).__name__ for x in fake_ipython.displayed] == ["Thinking", "Card"]
    shown = fake_ipython.widgets_shown[-1]
    assert "スマホは持っていっていい？" in shown._repr_html_()


def test_async_handler_is_awaited_on_the_ipywidgets_path(fake_ipython, monkeypatch):
    fake_ipywidgets(monkeypatch)
    make_async_form()._ipython_display_()
    text_box, button = widgets_of(fake_ipython)
    text_box.value = "2の8乗は？"
    button.fn(None)
    assert "2の8乗は？" in output_html(fake_ipython)


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

    # 諦めたときも、Python の英語のメッセージ（could not convert string to
    # float）ではなく、読んで分かる言葉にする
    answers = iter(["a", "b", "c"])
    with pytest.raises(ValueError, match="数を入力してください"):
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


# --- 待っているあいだの表示 -------------------------------------------------


class _Recorder:
    """display された順番を記録する、Output の代わり。"""

    def __init__(self):
        self.shown = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _drive(result, pending=None, into=None):
    """display_result を回し、表示されたものを順に返す。"""
    import library_hiroba._forms as forms

    shown = []

    class FakeDisplay:
        def __call__(self, obj, display_id=None):
            shown.append(obj)
            return self

        def update(self, obj):
            shown.append(obj)

    fake = FakeDisplay()
    module = types.ModuleType("IPython.display")
    module.display = fake
    module.clear_output = lambda wait=False: None
    old = sys.modules.get("IPython.display")
    sys.modules["IPython.display"] = module
    try:
        forms.display_result(result, into=into, pending=pending)
        while forms._PENDING:
            asyncio.get_event_loop_policy().new_event_loop()
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    asyncio.gather(*list(forms._PENDING), return_exceptions=True)
                )
            finally:
                loop.close()
    finally:
        if old is not None:
            sys.modules["IPython.display"] = module if old is None else old
    return shown


def test_pending_is_shown_before_the_answer():
    """押した直後に「考え中」、答えが来たら差し替わること。"""

    async def slow():
        await asyncio.sleep(0)
        return ui.card("答え", "3です")

    shown = _drive(slow(), pending=ui.thinking("考え中"))
    assert len(shown) == 2
    assert isinstance(shown[0], ui.Widget)
    assert "hui-thinking" in shown[0]._repr_html_()
    assert "3です" in shown[1]._repr_html_()


def test_a_synchronous_answer_skips_the_pending_step():
    """待たないなら「考え中」を挟む意味がない。"""
    shown = _drive(ui.card("すぐ出る"), pending=ui.thinking())
    assert len(shown) == 1
    assert "すぐ出る" in shown[0]._repr_html_()


def settle(timeout=5.0):
    """送信のために立ち上がったスレッドが終わるのを待つ。"""
    import time

    from library_hiroba import _forms

    limit = time.monotonic() + timeout
    while _forms._WORKERS and time.monotonic() < limit:
        time.sleep(0.01)
    assert not _forms._WORKERS, "送信の処理が終わらない"


def test_streaming_reaches_the_output_without_the_loop_being_pumped(fake_ipython, monkeypatch):
    """Colab と同じ条件で送信する。ここが動かないと「押しても何も出ない」（F1）。

    Colab はループが回っている状態で押下を配るが、セルの実行が終わっている
    あいだそのループを回していない。予約したタスクは順番待ちのまま止まる。
    そこで**押したあとループに一切順番を渡さず**、それでも結果が届くかを見る。
    ensure_future に戻すと、ここが落ちる。
    """
    fake_ipywidgets(monkeypatch)

    async def handler(question):
        for chunk in ["こ", "んにちは"]:
            await asyncio.sleep(0)
            yield ui.card(question, chunk)

    async def colab():
        ui.form(handler, ui.field("question", label=""))._ipython_display_()
        text_box, button = widgets_of(fake_ipython)
        text_box.value = "やあ"
        button.fn(None)
        # ここで await しない。Colab のループが止まっているのと同じ状態にする

    asyncio.run(colab())  # ループごと終了する
    settle()
    html = output_html(fake_ipython)
    assert "やあ" in html and "んにちは" in html


def test_a_failing_handler_says_so_instead_of_going_quiet(fake_ipython, monkeypatch):
    """handler が落ちたとき、黙って何も出ないのがいちばん困る（F1）。"""
    fake_ipywidgets(monkeypatch)

    async def handler(question):
        raise RuntimeError("わざと落とす")
        yield  # 非同期ジェネレータにするため（ここへは来ない）

    async def colab():
        ui.form(handler, ui.field("question", label=""))._ipython_display_()
        _text_box, button = widgets_of(fake_ipython)
        button.fn(None)

    asyncio.run(colab())
    settle()
    assert "わざと落とす" in output_html(fake_ipython)


def test_bad_input_is_reported_on_the_widgets_path(fake_ipython, monkeypatch):
    """数の欄に文字が入っていても、押した人に理由が見えること（F1）。"""
    fake_ipywidgets(monkeypatch)
    ui.form(lambda age: ui.card(age), ui.field("age", kind="number"))._ipython_display_()
    number_box, button = widgets_of(fake_ipython)
    number_box.value = "数ではない"  # 本物は float だが、検証ツールで壊されうる
    button.fn(None)
    assert "数を入力してください" in output_html(fake_ipython)


def test_the_widgets_path_carries_the_library_styling(fake_ipython, monkeypatch):
    """ipywidgets 経路にも CSS を届ける。素の見た目のまま出さない（F2）。"""
    fake_ipywidgets(monkeypatch)
    make_form()._ipython_display_()
    box = fake_ipython.displayed[0]
    text_box, button = widgets_of(fake_ipython)
    # base_css は配色や角丸を .hui に載せている。付け忘れると var(--hui-accent) が
    # 解決できず、色も枠も無い素の ipywidgets に戻る
    assert box.classes == ["hui", "hui-wform"]
    assert "hui-wfield" in text_box.classes
    assert "hui-wsubmit" in button.classes
    # 部品側の <style> が出ない経路なので、フォーム自身が CSS を持って出る
    style = box["vbox"][0].value
    assert style.startswith("<style>")
    assert ".hui-wsubmit" in style and "--hui-accent" in style
    # 変数を配っているセレクタが箱に付いていること（ここがずれると全部無色になる）
    assert ".hui{" in style.replace(" ", "")


def test_a_generator_handler_replaces_the_display_each_time():
    """一文字ずつ出すための経路。yield ごとに差し替わること。"""

    async def stream():
        text = ""
        for chunk in ["こ", "ん", "に", "ちは"]:
            text += chunk
            await asyncio.sleep(0)
            yield ui.card("答え", text)

    shown = _drive(stream(), pending=ui.thinking())
    assert len(shown) == 5  # 考え中 + 4回
    bodies = [s._repr_html_() for s in shown[1:]]
    assert "こ<" in bodies[0] or "こ" in bodies[0]
    assert "こんにちは" in bodies[-1]


def test_form_shows_thinking_by_default():
    f = ui.form(lambda q: q, ui.field("q"))
    assert f.pending is not None
    assert "hui-thinking" in f.pending._repr_html_()


def test_pending_can_be_a_word_or_turned_off():
    assert "AI が考えています" in ui.form(
        lambda q: q, ui.field("q"), pending="AI が考えています"
    ).pending._repr_html_()
    assert ui.form(lambda q: q, ui.field("q"), pending=None).pending is None
    custom = ui.card("待ってね")
    assert ui.form(lambda q: q, ui.field("q"), pending=custom).pending is custom


# --- PyHiroba 本体との受け渡し ---------------------------------------------


def test_submit_converts_values_like_the_other_paths():
    """本体は文字列しか送れない。数値欄は float にしてから handler へ渡す。

    揃えないと、同じ ui.form(...) が環境ごとに違う型を渡す。
    ipywidgets は FloatText なので float、ブラウザの input は常に文字列。
    """
    seen = {}

    def handler(age, name, size):
        seen.update(age=age, name=name, size=size)
        return ui.card("ok")

    f = ui.form(
        handler,
        ui.field("age", kind="number"),
        ui.field("name"),
        ui.field("size", kind="choice", choices=["小", "大"]),
    )
    f.submit(age="10", name="佐藤", size="大")
    assert seen["age"] == 10.0 and isinstance(seen["age"], float)
    assert seen["name"] == "佐藤"
    assert seen["size"] == "大"


def test_submit_accepts_values_that_are_already_typed():
    """ipywidgets 経路の float をそのまま渡されても壊れないこと。"""
    seen = {}
    f = ui.form(lambda age: seen.update(age=age), ui.field("age", kind="number"))
    f.submit(age=10.0)
    assert seen["age"] == 10.0


def test_submit_ignores_values_the_form_did_not_ask_for():
    """本体は画面の data-hui-field を集めて呼ぶが、画面は書き換えられる。

    素通しすると、検証ツールで足した欄が handler の引数を決められてしまう。
    何を受け取るかは、教材に書かれた Python のほうを正とする。
    """
    seen = {}

    def handler(question):
        seen.update(question=question)
        return ui.card("ok")

    f = ui.form(handler, "question")
    f.submit(question="ほんとうの入力", api_key="盗みたい値")
    assert seen == {"question": "ほんとうの入力"}


def test_submit_still_refuses_when_a_field_is_missing():
    """余分を捨てるようにしても、足りないほうは見逃さないこと。"""
    f = ui.form(lambda question: question, "question")
    with pytest.raises(ValueError, match="入力値が足りません"):
        f.submit(nothing="x")


def test_submit_says_which_field_was_wrong():
    f = ui.form(lambda age: age, ui.field("age", label="年れい", kind="number"))
    with pytest.raises(ValueError, match="年れい: 数を入力してください"):
        f.submit(age="じゅう")


def test_submit_rejects_a_choice_outside_the_list():
    f = ui.form(lambda size: size, ui.field("size", label="大きさ", kind="choice", choices=["小"]))
    with pytest.raises(ValueError, match="大きさ:"):
        f.submit(size="特大")


def test_clear_on_submit_is_marked_in_the_html():
    """本体が入力欄を空にするかどうかを、HTML から判断できること。"""
    assert 'data-hui-clear="true"' in ui.form(
        lambda q: q, ui.field("q"), clear_on_submit=True
    ).fragment()
    assert "data-hui-clear" not in ui.form(lambda q: q, ui.field("q")).fragment()


def test_pending_html_is_available_to_the_host():
    """本体が押した直後に出す「考え中」を、Colab と同じ見た目で取り出せること。"""
    f = ui.form(lambda q: q, ui.field("q"))
    assert "hui-thinking" in f.pending_html()
    assert f.pending_html().startswith('<div class="hui">')
    assert ui.form(lambda q: q, ui.field("q"), pending=None).pending_html() == ""


def test_a_failure_while_displaying_is_not_swallowed(fake_ipython, monkeypatch):
    """押下処理から出た例外は戻る先が無く、Colab では跡形もなく消える（F1）。

    submit() だけでなく display_result() まで囲っていないと、
    「押しても何も起きない」だけが残る。
    """
    fake_ipywidgets(monkeypatch)
    monkeypatch.setattr(
        "library_hiroba._forms.display_result",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("表示のときに落ちた")),
    )
    make_form()._ipython_display_()
    _text_box, button = widgets_of(fake_ipython)
    button.fn(None)  # 例外が外へ抜けないこと
    assert "表示のときに落ちた" in output_html(fake_ipython)


def test_a_number_field_refuses_a_default_that_is_not_a_number():
    """数の欄の既定値は、作った時点で確かめること（B-2）。

    以前は ``ui.field()`` を素通りし、PyHiroba では空欄として動き、Colab では
    ipywidgets の FloatText が**表示の瞬間に**落ちていた。環境で挙動が割れる
    うえ、traceback は ``ui.field()`` を書いた行ではなく表示の行を指す。
    """
    with pytest.raises(ValueError, match="default"):
        ui.field("n", kind="number", default="abc")
    # 空（既定）と数はそのまま通る
    assert ui.field("n", kind="number").default == ""
    assert ui.field("n", kind="number", default=5).default == 5


# --- 2026-09 の監査で見つかったもの（本物の ipywidgets を相手にする）----------


def real_form(monkeypatch, handler, *fields, **kwargs):
    """本物の ipywidgets でフォームを出し、(入力欄, ボタン, 出力欄) を返す。

    手書きの代役では、押下から表示までの本当の経路（別スレッド・Output への
    書き込み・容器に入れたときの取りこぼし）が再現できない。
    """
    widgets = require_ipywidgets()
    import IPython.display as module

    caught: list = []

    def display(*objects, **options):
        if options.get("raw"):
            return
        for obj in objects:
            if hasattr(obj, "_ipython_display_"):
                obj._ipython_display_()
            else:
                caught.append(obj)

    monkeypatch.setattr(module, "display", display)
    form = kwargs.pop("form", None) or ui.form(handler, *fields, **kwargs)
    (kwargs.pop("container", None) or form)._ipython_display_()
    box = next(c for c in caught if isinstance(c, widgets.VBox))
    children = list(box.children)
    return (
        next(c for c in children if isinstance(c, (widgets.Text, widgets.Textarea))),
        next(c for c in children if isinstance(c, widgets.Button)),
        next(c for c in children if isinstance(c, widgets.Output)),
        caught,
    )


def seen(output) -> list[str]:
    """Output に入っているものを、文字だけにして並べる。"""
    texts = []
    for item in output.outputs:
        raw = str(item.get("data", {}).get("text/html", item.get("text", "")))
        raw = re.sub(r"<style>.*?</style>", "", raw, flags=re.S)
        texts.append(" ".join(re.sub(r"<[^>]+>", " ", raw).split()))
    return texts


def test_a_form_inside_a_container_is_still_registered():
    """容器に入れても、本体から引き当てられること（H-1・PyHiroba 側）。

    登録が ``_repr_html_`` にあったため、``ui.stack(card, form)`` では
    ``Container.fragment()`` が子の ``fragment()`` を呼んで登録を飛ばし、
    ``get_form()`` が None を返していた。本体の worker は None なら黙って戻るので、
    ボタンは描かれているのに押しても何も起きなかった。
    """
    form = make_form()
    page = ui.stack(ui.card("説明", "下に入れてね"), form)
    assert f'data-hui-submit="{form.form_id}"' in page._repr_html_()
    assert ui.get_form(form.form_id) is form, "容器に入れると引き当てられません"


def test_a_form_inside_a_container_becomes_a_real_widget(monkeypatch):
    """容器に入れても Colab では ipywidgets として出ること（H-1・Colab 側）。

    1枚の HTML にまとめると、JavaScript の無いボタンが描かれるだけになる。
    """
    form = make_form()
    field, button, output, caught = real_form(
        monkeypatch, None, form=form, container=ui.stack(ui.card("説明", "…"), form)
    )
    assert any(type(c).__name__ == "Card" for c in caught), "容器の中身が出ていません"
    field.value = "やま"
    button.click()
    settle()
    assert seen(output), "押しても何も起きませんでした"


def test_a_container_without_a_form_is_still_one_html(monkeypatch):
    """フォームが無い容器は、これまでどおり HTML 1枚で出ること（H-1）。"""
    require_ipywidgets()
    import IPython.display as module

    caught: list = []
    monkeypatch.setattr(module, "display", lambda *a, **k: caught.append((a, k)))
    ui.stack(ui.card("あ"), ui.card("い"))._ipython_display_()
    assert len(caught) == 1
    bundle, options = caught[0]
    assert options.get("raw") and "hui-stack" in bundle[0]["text/html"]


def test_an_older_submission_does_not_overwrite_a_newer_answer(monkeypatch):
    """2回押したとき、遅い1回目が新しい答えを上書きしないこと（H-3）。

    押下ごとに別スレッドが立ち、古い実行は止められない。遅い1回目が後から
    返ると、**新しい質問の下に前の質問の答えが残る**。生徒には取り違えに見える。
    """

    async def handler(q):
        await asyncio.sleep(0.6 if q == "おそい" else 0.0)
        return ui.card("答え", f"「{q}」への答え")

    async def drive():
        # **ループが回っている状態で押す。** ここを素のまま押すと
        # display_result は asyncio.run を選び、押下が直列化されて重ならない
        # （重ならなければ、この不具合は起きないので検査にならない）
        field, button, output, _ = real_form(monkeypatch, handler, ui.field("q"))
        field.value = "おそい"
        button.click()
        await asyncio.sleep(0.05)
        field.value = "はやい"
        button.click()
        await asyncio.sleep(1.2)
        return seen(output)

    assert asyncio.run(drive()) == ["答え 「はやい」への答え"]


def test_a_stream_that_says_nothing_does_not_leave_thinking_on_screen(monkeypatch):
    """1つも出さずに終わったとき、そう言うこと（M-3）。

    「考え中」が出たまま残る／pending=None だと画面が何も変わらない。
    どちらも故障と見分けが付かない。
    """

    async def nothing(q):
        if False:  # pragma: no cover — 1つも yield しない形を作るため
            yield
        return

    for pending in (ui.thinking(), None):
        _field, button, output, _ = real_form(
            monkeypatch, nothing, ui.field("q"), pending=pending
        )
        button.click()
        settle()
        assert seen(output), "画面が何も変わりません"
        assert "考え中" not in " ".join(seen(output)), f"考え中が残っています: {seen(output)}"
        assert "返ってきませんでした" in " ".join(seen(output))


def test_a_generator_handler_without_async_still_works(monkeypatch):
    """``yield`` で書いて ``async`` を付け忘れても動くこと（L-2）。"""

    def steps(q):
        yield ui.card("答え", q)

    field, button, output, _ = real_form(monkeypatch, steps, ui.field("q"))
    field.value = "やま"
    button.click()
    settle()
    assert seen(output) == ["答え やま"], f"実際: {seen(output)}"


def test_an_empty_number_field_behaves_the_same_in_both_paths(monkeypatch):
    """数の欄を触らずに送ると、両環境で同じことが起きること（M-6）。

    Colab は FloatText が空を持てないため 0 として黙って進み、PyHiroba は
    「数を入力してください」で止まっていた。同じコードの結果が環境で変わる。
    """
    field_spec = ui.field("n", label="点数", kind="number")
    with pytest.raises(ValueError, match="数を入力してください"):
        ui.form(lambda n: n, field_spec).submit(n="")

    field, button, output, _ = real_form(monkeypatch, lambda n: ui.card("受けた", repr(n)), field_spec)
    assert field.value == "", "Colab 側の初期値が空ではありません"
    button.click()
    settle()
    shown = " ".join(seen(output))
    assert "数を入力してください" in shown, f"実際: {seen(output)}"
    # traceback ではなく、PyHiroba と同じ読める文言で出すこと。traceback にも
    # 同じ文が含まれるので、そこを見ないと「出ている」と誤判定する
    assert "Traceback" not in shown, f"traceback が出ています: {seen(output)}"
    field.value = "90"
    button.click()
    settle()
    assert seen(output) == ["受けた 90.0"], f"実際: {seen(output)}"


# --- Colab での見た目（ipywidgets の決め打ちとぶつかる分）---------------------


def widgets_css() -> str:
    """``widgets`` の CSS を、空白を無視して比べられる形にする。"""
    from library_hiroba._css import COMPONENT_CSS

    return re.sub(r"\s+", "", COMPONENT_CSS["widgets"])


@pytest.mark.parametrize(
    ("declaration", "why"),
    [
        # セレクタまで含めて見る。height:auto!important だけだと、もとからある
        # .hui-wsubmit の指定に当たって素通りする（見張りになっていなかった）
        (
            '.hui-wfieldtextarea{height:auto!important}',
            "入力欄の高さ 28px を外さないと、文字の入る高さが 10px しか残らず上下が切れる",
        ),
        ("flex:00auto!important", "縦並びにすると ipywidgets の flex:1 1 … が縦に伸び、選択欄が 148px に膨らむ"),
        ("flex-direction:column!important", "名前を入力欄の上に出さないと、幅 80px の欄で「…」になる"),
        ("white-space:normal!important", "名前を折り返さないと、長い名前が切れたままになる"),
        ("align-self:flex-start!important", "VBox は子を横いっぱいに伸ばすので、width:auto では止まらない"),
    ],
)
def test_the_colab_look_neutralises_what_ipywidgets_fixes(declaration, why):
    """ipywidgets の決め打ちを打ち消す指定が残っていること。

    ここは Colab で開いた人にしか見えず、例外にもならない。実際に描いて測るのは
    ``tools/check_widget_css.py``（ブラウザが要るので CI では回さない）。
    こちらは、その打ち消しが消えていないことだけを見張る。
    """
    assert declaration in widgets_css(), why


def test_the_title_colour_is_forced_inside_the_form():
    """題名の色をこちらで決めていること。

    Colab のダークでは ipywidgets の文字色のもとが明るくなる。題名は白い枠の上に
    乗るので、上書きしないと地との差が 1.21:1 になって読めない。
    """
    css = widgets_css()
    assert ".hui-wform.widget-html-content" in css or ".hui-wform.jupyter-widget-html" in css, (
        "widgets.HTML（題名）の色を上書きする規則がありません"
    )
    assert "color:var(--hui-ink)!important" in css
