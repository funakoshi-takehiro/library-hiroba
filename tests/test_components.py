from __future__ import annotations

import re

import pytest
from conftest import has_rule
from sanitize_check import check_html

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
    # 書体は名前で指定する。PyHiroba はページ側が読み込み済みなのでこれで揃い、
    # 持っていない環境（Colab など）は system-ui に落ちる。取りには行かない。
    assert "Zen Kaku Gothic New" in rendered
    assert "fonts.googleapis.com" not in rendered
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


def test_conversation_stacks_up_in_the_right_roles():
    """say / reply / note が、それぞれの向きの吹き出しになる（C1）。"""
    talk = ui.conversation(names={"assistant": "ボット"})
    talk.say("こんにちは")
    talk.reply("やあ！")
    talk.note("ここから練習です")
    html = talk._repr_html_()
    for role in ("user", "assistant", "note"):
        assert html.count(f"hui-msg hui-msg-{role}") == 1
    assert "ボット" in html
    assert check_html(html) == []


def test_conversation_can_be_shown_while_still_empty():
    """最初のセルで作って、次のセルから足していく書き方を通す（C1）。

    ui.chat() は空を受け付けないので、ここが分かれ目になる。
    """
    talk = ui.conversation()
    assert len(talk) == 0
    html = talk._repr_html_()
    assert '<div class="hui-chat"></div>' in html
    assert check_html(html) == []
    with pytest.raises(ValueError, match="1つ以上"):
        ui.chat([])  # こちらは今までどおり受け付けない


def test_conversation_messages_can_be_handed_to_chat():
    """ためた会話は ui.chat() にそのまま渡せる形であること（C1）。"""
    talk = ui.conversation()
    talk.say("やあ").reply("どうも")  # つなげても書ける
    assert talk.messages == [
        {"role": "user", "content": "やあ"},
        {"role": "assistant", "content": "どうも"},
    ]
    assert "やあ" in ui.chat(talk.messages)._repr_html_()


def test_conversation_messages_is_a_copy():
    """写しを返す。直接 append しても増えないほうが、間違いに気付ける（C1）。"""
    talk = ui.conversation()
    talk.say("やあ")
    talk.messages.append({"role": "user", "content": "増えないはず"})
    talk.messages[0]["content"] = "書き換わらないはず"
    assert talk.messages == [{"role": "user", "content": "やあ"}]


def test_conversation_rejects_an_unknown_role_when_it_is_added():
    """表示のときまで持ち越さず、足した時点で止める（C1）。"""
    with pytest.raises(ValueError, match="role は"):
        ui.conversation([{"role": "せんせい", "content": "やあ"}])
    talk = ui.conversation()
    with pytest.raises(ValueError, match="role は"):
        talk._add("system", "やあ")


def test_conversation_carries_the_css_of_what_is_inside_it():
    """吹き出しに部品を入れたとき、その CSS も一緒に出ること（C1）。"""
    talk = ui.conversation()
    talk.reply(ui.card("答え", "本文"))
    html = talk._repr_html_()
    assert "hui-card" in html
    assert has_rule(html, ".hui-card")
    assert check_html(html) == []


def test_conversation_clears():
    talk = ui.conversation()
    talk.say("やあ").reply("どうも")
    assert len(talk.clear()) == 0
    assert talk.messages == []


def test_html_rejects_what_pyhiroba_would_strip():
    """PyHiroba 側で消えるものは、書いた時点で止める（S2）。

    止めないと Colab では動いて本番では動かず、書いた本人は気付けない。
    """
    for raw in [
        "<script>alert(1)</script>",
        '<iframe src="http://example.com"></iframe>',
        '<form action="http://example.com"><input></form>',
        '<object data="x.swf"></object>',
        '<embed src="x"/>',
        '<link rel="stylesheet" href="http://example.com/x.css">',
        '<div onclick="steal()">押して</div>',
        '<a href="javascript:alert(1)">ここ</a>',
    ]:
        with pytest.raises(ValueError, match="PyHiroba では表示できない"):
            ui.html(raw)


def test_html_rejection_survives_case_and_entities():
    """大文字や実体参照で隠しても素通りしない（S2）。"""
    with pytest.raises(ValueError, match="PyHiroba では表示できない"):
        ui.html("<SCRIPT>alert(1)</SCRIPT>")
    with pytest.raises(ValueError, match="PyHiroba では表示できない"):
        ui.html('<div ONCLICK="x()">a</div>')
    # &#106; は j。HTMLParser が属性値を復元してから渡すので拾える。
    # 正規表現で書き直すとここが落ちる
    with pytest.raises(ValueError, match="PyHiroba では表示できない"):
        ui.html('<a href="&#106;avascript:alert(1)">a</a>')
    # 途中に空白を挟んでも URL としては通ってしまう
    with pytest.raises(ValueError, match="PyHiroba では表示できない"):
        ui.html('<a href="java\nscript:alert(1)">a</a>')


def test_html_says_what_it_found():
    """何が引っかかったのか分からないと直せない（S2）。"""
    with pytest.raises(ValueError) as caught:
        ui.html('<div onclick="x()"><script>y</script></div>')
    message = str(caught.value)
    assert "<script> タグ" in message
    assert "onclick 属性" in message
    # 直し方の手がかりも添える
    assert "IPython.display.HTML" in message


def test_html_stays_a_usable_escape_hatch():
    """逃げ道として使えなくなるほど厳しくしない（S2）。

    id も style も、どちらの環境でも残るので触らない。
    """
    ui.html('<div id="x" style="color: red; transform: rotate(3deg)">やあ</div>')
    ui.html('<a href="https://example.com" target="_blank">リンク</a>')
    ui.html('<img src="data:image/gif;base64,R0lGOD" alt="">')
    ui.html("<div><span>閉じ忘れ")  # 断片の中で閉じるのでホストには漏れない
    # css 側の検査とは別軸。scoped を外しても raw は見る
    with pytest.raises(ValueError, match="PyHiroba では表示できない"):
        ui.html("<script>x</script>", css="p { margin: 0 }", scoped=False)


def test_dangerous_tag_list_matches_the_sanitize_checker():
    """一覧が2か所にあるので、ずれたら気付けるようにする（S2）。

    片方から import すると、検査の正しさをテスト自身が保証できなくなる。
    独立に書いたうえで、一致することをここで確かめる。
    """
    import sanitize_check

    from library_hiroba._components import DANGEROUS_TAGS, URL_ATTRS

    assert DANGEROUS_TAGS == sanitize_check.FORBIDDEN_TAGS
    assert URL_ATTRS == sanitize_check.URL_ATTRS


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


# --- 監査で見つかった取りこぼし -------------------------------------------


def test_headers_may_be_any_sequence():
    """headers を何度もなぞるので、生成器で渡されても結果が変わらないこと。

    以前は最初の1行で尽きて、2行目以降が黙って空欄になっていた。表は出るので
    気付けず、生徒の点数が消えたまま配られてしまう。
    """
    rows = [{"名前": "佐藤", "点": 90}, {"名前": "鈴木", "点": 85}]
    from_list = ui.table(rows, headers=["名前", "点"])._repr_html_()
    from_generator = ui.table(rows, headers=(h for h in ["名前", "点"]))._repr_html_()
    from_tuple = ui.table(rows, headers=("名前", "点"))._repr_html_()
    assert from_generator == from_list == from_tuple
    assert "85" in from_generator


# --- 外部への通信 -----------------------------------------------------------


def test_the_font_is_the_only_thing_fetched_from_outside():
    """部品が外に取りに行くのは書体だけであること。

    閉じた校内ネットワークで動く前提なので、取得先が増えたら気付けるようにする。
    """
    import re as _re

    from library_hiroba._css import BASE_CSS, COMPONENT_CSS

    everything = BASE_CSS + "".join(COMPONENT_CSS.values())
    urls = _re.findall(r"https?://[^)'\"]+", everything)
    assert [u for u in urls if "fonts.googleapis.com" not in u] == []


def test_nothing_is_fetched_by_default():
    """既定では外部への通信が一切起きないこと。

    PyHiroba ではページ側が同じ書体を持っているので、取りに行かなくても揃う。
    効くのは Colab だけで、そちらは揃っている必要がない。
    """
    rendered = ui.card("目標", "本文")._repr_html_()
    assert "@import" not in rendered
    assert "googleapis" not in rendered
    # 見た目の土台は残っている（CSS ごと落としていない）
    assert ".hui-card" in rendered
    assert "--hui-accent" in rendered
    # 書体の指定そのものは残す。PyHiroba 側が持っていればこれで揃う
    assert "Zen Kaku Gothic New" in rendered


def test_the_font_can_be_turned_on_for_colab():
    from library_hiroba import ui as _ui

    try:
        _ui.use_web_font(True)
        assert "fonts.googleapis.com" in _ui.card("a")._repr_html_()
    finally:
        _ui.use_web_font(False)


# --- 監査で見つかった「黙って間違う」書き方 ---------------------------------


@pytest.mark.parametrize("factory", ["columns", "stack", "show"])
def test_a_list_of_parts_is_read_as_the_parts(factory):
    """``ui.columns([a, b])`` が部品2つとして読まれること（B-1）。

    ``ui.chat()`` と ``ui.table()`` はリストを受け取るので、こう書くのは自然な
    間違い。以前は可変長引数にリスト1個として届き、例外にもならずに画面へ
    ``[<library_hiroba.Card>, <library_hiroba.Card>]`` という文字が出ていた。
    """
    widget = getattr(ui, factory)([ui.card("あ"), ui.card("い")])
    html = widget._repr_html_()
    assert "library_hiroba.Card" not in html, "リストの文字列表現が画面に出ています"
    assert "あ" in html and "い" in html


@pytest.mark.parametrize("factory", ["columns", "stack"])
def test_the_old_way_of_writing_still_works(factory):
    """可変長引数で並べる従来の書き方は変わらないこと（B-1）。"""
    html = getattr(ui, factory)(ui.card("あ"), ui.card("い"))._repr_html_()
    assert "あ" in html and "い" in html


def test_widths_are_matched_against_the_list_contents():
    """リストで渡したときも、widths の数はその中身と照合されること（B-1）。"""
    with pytest.raises(ValueError, match="部品の数（2）"):
        ui.columns([ui.card("あ"), ui.card("い")], widths=[1])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_progress_refuses_values_that_are_not_real_numbers(bad):
    """NaN と無限大を止めること（B-4）。

    ``min``/``max`` は NaN との比較がすべて False になるため、素通りさせると
    **0% という、もっともらしい嘘**が画面に出る。平均のもとが空だった、と
    いった計算の誤りがそこで隠れる。
    """
    with pytest.raises(ValueError):
        ui.progress(bad, 10)
    with pytest.raises(ValueError):
        ui.progress(1, bad)


@pytest.mark.parametrize(
    ("call", "argument"),
    [
        (lambda: ui.progress("abc", 10), "value"),
        (lambda: ui.progress(1, "abc"), "max"),
        (lambda: ui.columns(ui.card("あ"), widths=["x"]), "widths"),
    ],
)
def test_a_bad_number_says_which_argument_it_was(call, argument):
    """数でない値を渡したとき、どの引数の話か分かること（B-3）。

    素の ``could not convert string to float: 'abc'`` では、部品を並べたセルの
    どこが悪いのか分からない。
    """
    with pytest.raises(ValueError, match=argument):
        call()


def test_ordinary_numbers_are_untouched():
    """直したことで、普通の値の見え方が変わっていないこと（B-3, B-4）。"""
    assert 'aria-valuenow="70"' in ui.progress(7, 10)._repr_html_()
    assert "flex: 2 1 0" in ui.columns(ui.card("あ"), ui.card("い"), widths=[2, 1])._repr_html_()
