from __future__ import annotations

import re

import pytest
from conftest import has_rule

import library_hiroba
from library_hiroba import ui


def test_version_is_well_formed():
    # 具体的な番号は書かない（リリースのたびにテストを直す必要がなくなる）。
    # 公開ワークフローが、この値とタグの一致を別途検証している。
    assert re.fullmatch(r"\d+\.\d+\.\d+", library_hiroba.__version__)


# --- card / alert -----------------------------------------------------------


def test_card_is_deterministic():
    a = ui.card("題", "本文", icon="[1]", footer="脚注")._repr_html_()
    b = ui.card("題", "本文", icon="[1]", footer="脚注")._repr_html_()
    assert a == b


def test_card_newline_becomes_br():
    assert "1行目<br>2行目" in ui.card("題", "1行目\n2行目")._repr_html_()


def test_alert_kinds_and_validation():
    assert 'class="hui-alert hui-alert-success"' in ui.alert("m", kind="success").fragment()
    assert "hui-alert-warning" not in ui.alert("m").fragment()
    with pytest.raises(ValueError):
        ui.alert("m", kind="fatal")


def test_alert_marks_are_text_glyphs_not_emoji():
    marks = {"info": "i", "success": "✓", "warning": "!", "danger": "×"}
    for kind, mark in marks.items():
        markup = ui.alert("m", kind=kind).fragment()
        assert f'<span class="hui-alert-icon" aria-hidden="true">{mark}</span>' in markup


# --- PyHiroba とのデザイン統一 ---------------------------------------------

# 部品の既定出力に含めない絵文字（PyHiroba は絵文字を使わない方針）
_EMOJI_SAMPLE = "🎯📈🔥⏱🐍✅⚠️ℹ️🚨👋"


def test_no_emoji_in_default_output():
    widgets = [
        ui.card("題", "本文", footer="脚注"),
        *[ui.alert("m", kind=k) for k in ("info", "success", "warning", "danger")],
        ui.quiz("q?", ["a", "b"], "a", explanation="解説"),
        ui.reveal("答え"),
        ui.progress(5, max=10, label="進捗"),
        ui.stat("正答率", 85, unit="%"),
        ui.badge("重要", color="red"),
        ui.table([{"名前": "佐藤", "得点": 90}]),
    ]
    for widget in widgets:
        rendered = widget._repr_html_()
        for char in _EMOJI_SAMPLE:
            assert char not in rendered, f"{type(widget).__name__} に絵文字 {char} がある"


def test_pyhiroba_design_tokens_and_font():
    rendered = ui.card("題")._repr_html_()
    assert "Zen Kaku Gothic New" in rendered  # PyHiroba と同じ書体
    assert "fonts.googleapis.com" in rendered  # 未読込環境向けの @import（失敗時は system-ui）
    assert "#028DAE" in rendered  # ライトのブランドティール
    assert "#35aecb" in rendered  # ダークのブランドティール
    assert re.search(r'font-feature-settings:\s*"palt"', rendered)


def test_table_css_outranks_pyhiroba_output_html_styles():
    # PyHiroba の .output-html table th（0,1,1）に負けないよう .hui を前置している
    rendered = ui.table([[1]], headers=["x"])._repr_html_()
    assert ".hui .hui-table th" in rendered
    assert "\n.hui-table th" not in rendered


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
    assert has_rule(with_exp, ".hui-reveal")
    assert "解説を見る" in with_exp
    assert not has_rule(without, ".hui-reveal")


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
    rendered = ui.stat("正答率", 85, unit="%", icon="*")._repr_html_()
    assert "hui-stat-unit" in rendered and "*" in rendered


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
    assert '<th scope="col">名前</th>' in rendered and '<th scope="col">備考</th>' in rendered
    assert "<td></td>" in rendered  # 1行目の「備考」は空セル


def test_table_from_lists_with_headers_and_caption():
    rendered = ui.table([[1, 2], [3, 4]], headers=["x", "y"], caption="表1")._repr_html_()
    assert "<caption>表1</caption>" in rendered
    assert '<th scope="col">x</th><th scope="col">y</th>' in rendered
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
    assert has_rule(card_html, ".hui-card")
    assert not has_rule(card_html, ".hui-quiz")
    assert ".hui-table" not in card_html


# --- chat -------------------------------------------------------------------


def test_chat_accepts_dicts_and_tuples():
    a = ui.chat([{"role": "user", "content": "こんにちは"}]).fragment()
    b = ui.chat([("user", "こんにちは")]).fragment()
    assert "hui-msg-user" in a and "こんにちは" in a
    assert a.replace("dict", "") and "hui-msg-user" in b


def test_chat_roles_and_names():
    markup = ui.chat(
        [("user", "質問"), ("assistant", "答え"), ("note", "メモ")],
        names={"user": "生徒", "assistant": "先生"},
    ).fragment()
    for role in ("user", "assistant", "note"):
        assert f"hui-msg-{role}" in markup
    assert "生徒" in markup and "先生" in markup


def test_chat_content_can_be_another_widget():
    rendered = ui.chat(
        [("assistant", ui.reveal("第9条の全文", summary="読んだ条文"))]
    )._repr_html_()
    assert "<details" in rendered
    assert has_rule(rendered, ".hui-reveal")  # 子の CSS もまとめて同梱される


def test_chat_validation():
    with pytest.raises(ValueError):
        ui.chat([])
    with pytest.raises(ValueError):
        ui.chat([("teacher", "未対応の役割")])


def test_chat_escapes_text():
    rendered = ui.chat([("user", "<script>alert(1)</script>")])._repr_html_()
    assert "<script" not in rendered.lower()
    assert "&lt;script&gt;" in rendered


# --- 監査で見つかった不具合の再発防止 ---------------------------------------


def test_falsy_values_are_still_shown():
    """0 や False は表示したい値。真偽判定で消してはいけない（B1）。"""
    assert "<span>0</span>" in ui.card(0, "本文").fragment()
    assert ">0<" in ui.alert("m", title=0).fragment()
    assert ">0<" in ui.stat("得点", 1, unit=0).fragment()
    assert ">0<" in ui.card(False, "本文").fragment().replace("False", "0")
    # None と空文字は今までどおり出さない
    assert "hui-card-title" not in ui.card(None, "本文").fragment()
    assert "hui-card-title" not in ui.card("", "本文").fragment()


def test_table_rejects_shapes_that_would_render_wrong():
    """渡し方の取り違えを黙って通すと、壊れた表が出る（B2）。"""
    with pytest.raises(ValueError, match="行の一覧"):
        ui.table({"名前": "佐藤", "得点": 90})
    with pytest.raises(ValueError, match="混ざって"):
        ui.table([{"a": 1}, [2]])
    with pytest.raises(ValueError, match="文字列"):
        ui.table(["abc"])


def test_table_pads_short_rows():
    """列数が足りない行は空欄で埋める（B3）。"""
    t = ui.table([[1, 2], [3]], headers=["a", "b"])
    assert t.rows == [[1, 2], [3, ""]]
    assert t.fragment().count("<td>") == 4


def test_scoped_css_must_stay_inside_its_scope():
    """} でスコープを抜ける CSS は受け付けない（S1）。"""
    with pytest.raises(ValueError, match="波括弧"):
        ui.html("x", css="} body { display: none } .x {")
    with pytest.raises(ValueError, match="波括弧"):
        ui.html("x", css=".a { color: red")  # 閉じ忘れ
    # 文字列やコメントの中の } は数えない
    ui.html("x", css='.a { content: "}" }')
    ui.html("x", css="/* } */ .a { color: red }")
    # 意図してページ全体に効かせる場合は scoped=False
    assert ui.html("x", css="} body {}", scoped=False)


def test_alert_kind_is_conveyed_to_screen_readers():
    """記号は aria-hidden なので、種類は言葉でも伝える（W2）。"""
    for kind, spoken in [("info", "お知らせ"), ("success", "できました"),
                         ("warning", "注意"), ("danger", "警告")]:
        assert f'<span class="hui-vh">{spoken}：</span>' in ui.alert("m", kind=kind).fragment()
    assert has_rule(ui.alert("m")._repr_html_(), ".hui .hui-vh")


def test_table_headers_have_scope():
    """列見出しとして読み上げられるようにする（W2）。"""
    assert '<th scope="col">a</th>' in ui.table([[1]], headers=["a"]).fragment()


def test_css_is_minified_but_intact():
    """出力ごとに CSS を同梱するため縮める。意味は変えない（W1）。"""
    from library_hiroba._css import BASE_CSS

    assert "\n  " not in BASE_CSS  # 余白が落ちている
    for token in ("#028DAE", "#35aecb", "Zen Kaku Gothic New", '[data-theme="dark"]'):
        assert token in BASE_CSS
    quiz = ui.quiz("q", ["a", "b"], "a")._repr_html_()
    assert "@supports" in quiz and "@media" in quiz  # @ルールは壊れていない
