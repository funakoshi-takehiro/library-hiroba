from __future__ import annotations

import pytest

import ui_hiroba as ui


def test_version():
    assert ui.__version__ == "0.1.0"


# --- card / alert -----------------------------------------------------------


def test_card_is_deterministic():
    a = ui.card("題", "本文", icon="🎯", footer="脚注")._repr_html_()
    b = ui.card("題", "本文", icon="🎯", footer="脚注")._repr_html_()
    assert a == b


def test_card_newline_becomes_br():
    assert "1行目<br>2行目" in ui.card("題", "1行目\n2行目")._repr_html_()


def test_alert_kinds_and_validation():
    assert 'class="hui-alert hui-alert-success"' in ui.alert("m", kind="success").fragment()
    assert "hui-alert-warning" not in ui.alert("m").fragment()
    with pytest.raises(ValueError):
        ui.alert("m", kind="fatal")


# --- quiz -------------------------------------------------------------------


def test_quiz_names_are_unique_per_instance():
    q1 = ui.quiz("q?", ["a", "b"], "a")
    q2 = ui.quiz("q?", ["a", "b"], "a")
    assert q1.name != q2.name
    assert q1._repr_html_().count(f'name="{q1.name}"') == 2


def test_quiz_answer_is_marked():
    markup = ui.quiz("2の8乗は？", choices=[128, 256, 512], answer=256).fragment()
    assert markup.count("hui-is-answer") == 1
    assert markup.count('type="radio"') == 3


def test_quiz_validation():
    with pytest.raises(ValueError):
        ui.quiz("q?", ["a", "b"], "c")  # answer が choices にない
    with pytest.raises(ValueError):
        ui.quiz("q?", ["a"], "a")  # 選択肢が少なすぎる
    with pytest.raises(ValueError):
        ui.quiz("q?", ["a", "a"], "a")  # 重複


def test_quiz_explanation_pulls_in_reveal_css():
    with_exp = ui.quiz("q?", ["a", "b"], "a", explanation="なぜなら")._repr_html_()
    without = ui.quiz("q?", ["a", "b"], "a")._repr_html_()
    assert ".hui-reveal {" in with_exp
    assert "解説を見る" in with_exp
    assert ".hui-reveal {" not in without


# --- reveal / progress / stat ----------------------------------------------


def test_reveal_structure():
    rendered = ui.reveal("答えは42", summary="開く")._repr_html_()
    assert "<details" in rendered and "<summary>開く</summary>" in rendered


def test_progress_clamps_and_aria():
    over = ui.progress(150, max=100)._repr_html_()
    under = ui.progress(-5)._repr_html_()
    half = ui.progress(5, max=10)._repr_html_()
    assert "width: 100%;" in over
    assert "width: 0%;" in under
    assert "width: 50%;" in half and 'aria-valuenow="50"' in half
    with pytest.raises(ValueError):
        ui.progress(1, max=0)


def test_progress_hide_value():
    assert "hui-progress-num" not in ui.progress(50, show_value=False).fragment()


def test_stat_unit_and_icon():
    rendered = ui.stat("正答率", 85, unit="%", icon="📈")._repr_html_()
    assert "hui-stat-unit" in rendered and "📈" in rendered


# --- columns / stack --------------------------------------------------------


def test_columns_dedupes_child_css():
    rendered = ui.columns(ui.stat("a", 1), ui.stat("b", 2), ui.stat("c", 3))._repr_html_()
    assert rendered.count(".hui-stat-value") == 1  # stat の CSS 定義は1回だけ
    assert rendered.count('class="hui-col"') == 3


def test_columns_widths():
    rendered = ui.columns(ui.stat("a", 1), ui.stat("b", 2), widths=[2, 1])._repr_html_()
    assert 'style="flex: 2 1 0;"' in rendered
    with pytest.raises(ValueError):
        ui.columns(ui.stat("a", 1), widths=[1, 2])
    with pytest.raises(ValueError):
        ui.columns(ui.stat("a", 1), widths=[0])


def test_stack_wraps_plain_strings():
    rendered = ui.stack(ui.card("a"), "ただの文字列")._repr_html_()
    assert "hui-text" in rendered and "ただの文字列" in rendered
    with pytest.raises(ValueError):
        ui.stack()


# --- badge / table ----------------------------------------------------------


def test_badge_colors():
    assert "hui-badge-red" in ui.badge("重要", color="red")._repr_html_()
    gray = ui.badge("メモ", color="gray")._repr_html_()
    assert "hui-badge-gray" not in gray  # gray は基本スタイルのみ
    with pytest.raises(ValueError):
        ui.badge("x", color="purple")


def test_table_from_dicts_derives_headers_in_order():
    rendered = ui.table(
        [{"名前": "佐藤", "得点": 90}, {"名前": "鈴木", "得点": 85, "備考": "追試"}]
    )._repr_html_()
    assert "<th>名前</th><th>得点</th><th>備考</th>" in rendered
    assert "<td></td>" in rendered  # 1行目の「備考」は空セル


def test_table_from_lists_with_headers_and_caption():
    rendered = ui.table([[1, 2], [3, 4]], headers=["x", "y"], caption="表1")._repr_html_()
    assert "<caption>表1</caption>" in rendered
    assert "<th>x</th><th>y</th>" in rendered
    assert "<td>3</td><td>4</td>" in rendered


def test_table_empty_raises():
    with pytest.raises(ValueError):
        ui.table([])


# --- html + css -------------------------------------------------------------


def test_html_css_is_scoped_by_default():
    w = ui.html('<div class="x">a</div>', css=".x { color: red; }")
    rendered = w._repr_html_()
    scope = w.scope_class
    assert scope is not None and scope.startswith("hui-raw-")
    assert f'class="hui-raw {scope}"' in rendered  # 中身のラッパーにスコープクラス
    assert f".{scope} {{" in rendered  # CSS はスコープクラスの中にネストされる
    assert ".x { color: red; }" in rendered


def test_html_css_scope_is_unique_per_instance():
    a = ui.html("x", css="b { color: red }")
    b = ui.html("x", css="b { color: red }")
    assert a.scope_class != b.scope_class


def test_html_css_unscoped_is_emitted_verbatim():
    w = ui.html("<p>a</p>", css="p { margin: 0 }", scoped=False)
    rendered = w._repr_html_()
    assert w.scope_class is None
    assert "p { margin: 0 }" in rendered
    assert 'class="hui-raw"' in rendered


def test_html_without_css_has_no_scope_class():
    w = ui.html("<b>x</b>")
    assert w.scope_class is None
    assert 'class="hui-raw"' in w.fragment()


def test_html_css_is_collected_through_containers():
    child = ui.html("<i>x</i>", css="i { color: red }")
    rendered = ui.stack(ui.card("t"), child)._repr_html_()
    assert "i { color: red }" in rendered


def test_html_css_duplicate_unscoped_blocks_are_deduped():
    a = ui.html("x", css=".g { color: red }", scoped=False)
    b = ui.html("y", css=".g { color: red }", scoped=False)
    rendered = ui.stack(a, b)._repr_html_()
    assert rendered.count(".g { color: red }") == 1


# --- show -------------------------------------------------------------------


def test_show_returns_widget_without_ipython():
    try:
        import IPython  # noqa: F401

        pytest.skip("IPython がある環境では display() に委譲されるため対象外")
    except ImportError:
        pass
    single = ui.show(ui.card("a"))
    assert isinstance(single, ui.Widget)
    multi = ui.show(ui.card("a"), "テキスト")
    assert isinstance(multi, ui.Widget)
    assert "hui-stack" in multi._repr_html_()
    with pytest.raises(ValueError):
        ui.show()


# --- CSS 出力の最小性 -------------------------------------------------------


def test_css_is_scoped_to_needed_components():
    card_html = ui.card("a")._repr_html_()
    assert ".hui-card {" in card_html
    assert ".hui-quiz {" not in card_html
    assert ".hui-table" not in card_html
