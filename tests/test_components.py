from __future__ import annotations

import re

import pytest
from conftest import has_rule, without_ipython
from sanitize_check import check_html

import library_hiroba
from library_hiroba import ui
from library_hiroba._components import css_stays_inside_scope, dangerous_html


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
    # セレクタの前にスコープクラスが付く。``.scope { ... }`` で包む（CSS ネスト）と
    # ネスト未対応の端末でユーザー CSS が1行も効かないので、前置でなければならない
    assert f".{scope} .x {{ color: red; }}" in rendered


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


def test_show_returns_widget_without_ipython(monkeypatch):
    without_ipython(monkeypatch)
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


def rendered(factory, *args, **kwargs) -> str:
    """部品を作って、表示される HTML を返す。

    ``ui.show()`` は IPython があると**その場で表示して None を返す**ので、
    返り値だけを見ると環境によってテストが通らない。表示された物を受け取る。
    """
    try:
        import IPython.display as module
    except ImportError:
        return factory(*args, **kwargs)._repr_html_()
    if module is None:  # without_ipython で隠された状態
        return factory(*args, **kwargs)._repr_html_()
    caught: list = []
    original = module.display
    module.display = lambda *shown, **_: caught.extend(shown)
    try:
        result = factory(*args, **kwargs)
    finally:
        module.display = original
    return (result if result is not None else caught[-1])._repr_html_()


@pytest.mark.parametrize("factory", ["columns", "stack", "show"])
def test_a_list_of_parts_is_read_as_the_parts(factory):
    """``ui.columns([a, b])`` が部品2つとして読まれること（B-1）。

    ``ui.chat()`` と ``ui.table()`` はリストを受け取るので、こう書くのは自然な
    間違い。以前は可変長引数にリスト1個として届き、例外にもならずに画面へ
    ``[<library_hiroba.Card>, <library_hiroba.Card>]`` という文字が出ていた。
    """
    html = rendered(getattr(ui, factory), [ui.card("あ"), ui.card("い")])
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


# --- 2026-09 の監査で見つかったもの ------------------------------------------


@pytest.mark.parametrize(
    "build",
    [
        lambda inner: ui.card("結果", inner),
        lambda inner: ui.reveal(inner, summary="答えを見る"),
        lambda inner: ui.alert(inner),
        lambda inner: ui.stat("順位", inner),
        lambda inner: ui.badge(inner),
        lambda inner: ui.thinking(inner),
    ],
)
def test_a_part_put_in_a_value_slot_is_drawn(build):
    """値の場所に部品を入れたら、描かれること（M-1）。

    以前は ``esc(str(value))`` を通って ``<library_hiroba.Table>`` という文字が
    画面に出ていた。``ui.chat()`` は前から部品を受け付けるので、一貫していない。
    """
    html = build(ui.table([{"名前": "佐藤"}]))._repr_html_()
    assert "library_hiroba." not in html, "部品の repr が画面に出ています"
    assert "佐藤" in html
    assert has_rule(html, ".hui-table"), "入れ子の部品の CSS が出ていません"


def test_a_value_slot_still_escapes_plain_text():
    """部品でない値は、これまでどおりエスケープされること（M-1）。"""
    html = ui.card("<b>題</b>", "1行\n2行")._repr_html_()
    assert "&lt;b&gt;" in html and "<b>題" not in html
    assert "<br>" in html, "改行が <br> になりません"


def test_headers_given_as_a_string_is_refused():
    """``headers`` に文字列を渡したら止まること（H-2）。

    ``list("名前")`` は ['名','前'] になり、列が1文字ずつに割れる。辞書の行は
    どのキーにも一致しないので、**中身が空欄のまま**表が出ていた。
    """
    with pytest.raises(ValueError, match="列名のリスト"):
        ui.table([{"名前": "佐藤", "点数": 90}], headers="名前")
    # 正しい書き方は通る
    assert ui.table([{"名前": "佐藤"}], headers=["名前"]).rows == [["佐藤"]]


def test_rows_given_as_bare_values_say_what_to_do():
    """行に値そのものを並べたとき、読める文言で止まること（M-7）。

    以前は ``'int' object is not iterable`` という英語だけが出ていた。
    文字列のリストには案内があったので、数値だけ取り残されていた。
    """
    with pytest.raises(ValueError, match="値そのもの"):
        ui.table([90, 85, 78], headers=["点数"])
    assert ui.table([[90], [85]], headers=["点数"]).rows == [[90], [85]]
    # タプルの行はこれまでどおり通る
    assert ui.table([(1, 2), (3, 4)]).rows == [[1, 2], [3, 4]]


@pytest.mark.parametrize("factory", ["columns", "stack", "show"])
def test_a_generator_of_parts_is_read_as_the_parts(factory):
    """ジェネレータ内包表記でも部品の並びとして読まれること（M-2）。"""
    html = rendered(getattr(ui, factory), (ui.badge(str(n)) for n in range(3)))
    assert "generator object" not in html, "ジェネレータの repr が画面に出ています"
    assert ">0<" in html and ">2<" in html


def test_a_length_without_a_unit_is_refused():
    """単位を書き忘れた長さを止めること（L-1）。

    CSS は ``gap: 8`` を宣言ごと捨てるので、例外にならないまま間隔だけが消える。
    """
    with pytest.raises(ValueError, match="単位"):
        ui.columns(ui.card("あ"), ui.card("い"), gap=8)
    with pytest.raises(ValueError, match="単位"):
        ui.stack(ui.card("あ"), gap="1.5")
    # 0 は単位が要らない。単位つきはこれまでどおり
    for good in ("0", 0, "12px", "1.5rem", "50%"):
        assert ui.stack(ui.card("あ"), gap=good)


# --- ブラウザと読み方が食い違う書き方 ---------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        '<!--><img src=x onerror="a=1">-->',
        '<!---><img src=x onerror="a=1">-->',
        '<!--><iframe srcdoc="x"></iframe>-->',
    ],
)
def test_empty_comment_does_not_hide_dangerous_html(payload):
    """``<!-->`` は HTML では中身の無いコメントとしてその場で閉じる。

    Python の HTMLParser は ``-->`` まで続くと読むため、後ろのタグを全部コメント
    本文として飲み込む。この食い違いを残すと、危険な書き方が検査を一つも通らずに
    すり抜け、サニタイザの無い Colab で実際に動く。
    """
    assert dangerous_html(payload), "ブラウザは本物のタグとして組み立てる"
    with pytest.raises(ValueError):
        ui.html(payload)


def test_a_normal_comment_is_still_not_flagged():
    """中身のあるコメントはブラウザでも動かないので、止めてはいけない（過検知の確認）。"""
    assert dangerous_html('<!-- <img src=x onerror="a=1"> -->') == []
    ui.html('<!-- <img src=x onerror="a=1"> -->')  # 例外にならない


def test_the_sanitize_checker_also_sees_through_empty_comments():
    """検査する側が同じ盲点を持つと、二重の防御が同時に無力になる。"""
    assert check_html('<div><!--><img src=x onerror="a=1">--></div>')


def test_a_newline_inside_a_css_string_does_not_escape_the_scope():
    """CSS では生の改行で文字列が終わる（仕様の bad-string-token）。

    「引用符が閉じるまで中身」と読むと、文字列の中だと思い込んだ ``}`` を
    ブラウザは本物として読み、CSS がスコープの外へ出てページ全体に効く。
    """
    css = 'content: "x\n} .hui-card { outline: 6px solid red } .zz {"'
    assert css_stays_inside_scope(css) is False
    with pytest.raises(ValueError):
        ui.html("<b>x</b>", css=css)


def test_a_backslash_keeps_a_css_string_going():
    """行末の ``\\`` は改行を打ち消す。正当な書き方を巻き込んで止めてはいけない。"""
    assert css_stays_inside_scope('content: "x\\\ny"') is True


def test_scoped_css_is_prefixed_and_never_nested():
    """``.scope { ... }`` で包むと、ネスト未対応の端末でユーザー CSS が1行も効かない。

    iPadOS 15〜16.3（Safari 16.5 未満）は GIGA 端末に実際に残っており、そこでは
    教材の棒グラフも吹き出しも素のテキストに落ちる。しかも何のエラーも出ない。
    """
    from library_hiroba._components import _css_top_level

    w = ui.html("<b>x</b>", css="b { color: red }\n.a, .b { margin: 0 }")
    out = w.extra_css()
    assert f".{w.scope_class} b" in out
    assert f".{w.scope_class} .a, .{w.scope_class} .b" in out
    for prelude, body in _css_top_level(out):
        if body is None or prelude.strip().startswith("@"):
            continue
        assert "{" not in body, f"ネストが残っている: {prelude.strip()[:40]}"


def test_scoped_css_keeps_at_rules_working():
    """``@media`` の中は前置しつつ、``@import`` はスコープに閉じ込められないので落とす。"""
    w = ui.html("<b>x</b>", css='@import url("x.css"); @media print { .a { color: red } }')
    out = w.extra_css()
    assert "@import" not in out
    assert "@media print" in out
    assert f".{w.scope_class} .a" in out


# --- 表の列数 ---------------------------------------------------------------


def test_table_stops_when_every_row_brings_its_own_key():
    """行ごとに違うキーを使うと、列が行数ぶん生えてセルが行数の2乗になる。

    ``[{語: 意味} for 語, 意味 in ペア]`` は単語帳でいちばん自然な書き方なので、
    黙って 100 万セルを作らせず、書き方を示して止める。
    """
    rows = [{f"w{i}": f"m{i}"} for i in range(1000)]
    with pytest.raises(ValueError, match="列が"):
        ui.table(rows)


def test_table_still_takes_a_wide_table_whose_rows_share_keys():
    """キーを全行で共有する幅広い表は、ますが2乗には増えないので止めない。

    列数だけで切ると、30行×365列（日付を列にした表）や1行だけの辞書まで
    巻き込んで止めてしまう。どちらも描ける大きさで、止める理由がない。
    """
    wide = [{f"d{i}": i for i in range(365)} for _ in range(30)]
    assert len(ui.table(wide).headers) == 365
    one_row = [{f"k{i}": i for i in range(500)}]
    assert len(ui.table(one_row).headers) == 500


def test_table_says_so_when_it_is_simply_too_big():
    """2乗の形ではないが端末が描けない大きさのときは、大きさとして言う。"""
    rows = [{f"c{j}": j for j in range(300)} for _ in range(1000)]
    with pytest.raises(ValueError, match="大きすぎます"):
        ui.table(rows)


def test_table_still_fills_in_rows_that_skip_a_key():
    """任意の項目が欠けている行は正当な使い方なので、空欄で並べる（止めない）。"""
    table = ui.table([{"名前": "佐藤", "点": 90}, {"名前": "鈴木"}])
    assert table.headers == ["名前", "点"]
    assert table.rows == [["佐藤", 90], ["鈴木", ""]]


# --- スマホ・タブレットでの見た目 -------------------------------------------


@pytest.mark.parametrize(
    ("key", "declaration", "why"),
    [
        (
            "chat",
            "overflow-wrap:anywhere",
            "切れ目の無い長い語で、user の発言が画面の左へ出る。"
            "右にあふれないのでスクロールバーも出ず、先頭が永久に読めない",
        ),
        (
            "columns",
            "margin-right:0",
            ".hui-stat が持つ右マージンが列の幅 100% と重なり、"
            "画面幅に関係なく 8px の横スクロールが出る",
        ),
        (
            "form",
            "font-size:16px",
            "16px 未満の入力欄にフォーカスすると、iOS がページを自動拡大して戻らない",
        ),
        (
            "form",
            "min-height:44px",
            "指で押す部分が 44px 未満（padding だけでは 37px にとどまる）",
        ),
    ],
)
def test_it_works_with_a_finger_on_a_small_screen(key, declaration, why):
    from library_hiroba._css import COMPONENT_CSS

    assert declaration in re.sub(r"\s+", "", COMPONENT_CSS[key]), why


def test_stale_module_is_told_on_the_html_paths_too(monkeypatch):
    """フォームを使わない生徒にも、入れ替えが効いていないことを知らせる。

    ``%pip install -U`` のあと再起動しないと、CSS も表も古いまま変わらない。
    以前は ``ui.form()`` でしか言っていなかったので、``ui.card`` や ``ui.quiz``
    しか使わない生徒は、直らない画面を見ながら何も知らされなかった。
    """
    import importlib.metadata as meta

    from library_hiroba import _core

    real = meta.version
    monkeypatch.setattr(
        meta, "version", lambda name: "9.9.9" if name == "library-hiroba" else real(name)
    )
    monkeypatch.setattr(_core, "_stale_unsaid", [True])

    first = ui.card("題", "本文")._repr_html_()
    assert "セッションを再起動する" in first
    assert ".hui-alert" in first, "警告の CSS を同梱しないと、枠も色も無い素の文字になる"

    # 一度言えば足りる。表や札を並べたセルで同じ警告が並ばないこと
    assert "セッションを再起動する" not in ui.table([[1, 2]])._repr_html_()


def test_nothing_is_said_when_the_version_matches(monkeypatch):
    from library_hiroba import _core

    monkeypatch.setattr(_core, "_stale_unsaid", [True])
    assert "セッションを再起動する" not in ui.card("題", "本文")._repr_html_()


@pytest.mark.parametrize(
    "payload",
    [
        # HTML では <![ は「最初の > で終わる偽コメント」。HTMLParser は ]]> を
        # 探すので、]]> の無い書き方で食い違い、後ろのタグが全部コメント扱いになる
        '<![CDATA[><img src=x onerror="a=1">',
        '<![CDATA[a>b<img src=x onerror="a=1">',
        '<!--><![CDATA[><img src=x onerror="a=1">',
    ],
)
def test_a_bogus_comment_does_not_hide_dangerous_html(payload):
    assert dangerous_html(payload), "ブラウザは本物のタグとして組み立てて動かす"
    with pytest.raises(ValueError):
        ui.html(payload)


def test_an_unclosed_cdata_is_not_flagged():
    """``>`` が一つも無ければブラウザも中身を組み立てないので、止めなくてよい。"""
    assert dangerous_html('<![CDATA[<img src=x onerror="a=1">'.replace(">", "", 1)) == []


# --- scope_css の字句解析（ブラウザと同じに読めているか）---------------------


@pytest.mark.parametrize(
    ("css", "why"),
    [
        (
            '[data-x="a&b"] { color: red }',
            "文字列の中の & をネスト参照と取り違えると、値が書き換わったうえに"
            "前置が付かず、トップレベルのルールとしてページ全体に効く",
        ),
        (
            '.a\\" { color: red }\n.hui-card { color: blue }',
            "セレクタの中のエスケープを見落とすと幻の文字列が開き、前置きの"
            "切り出しがずれて、ブラウザの再解析で次のルールがページ全体に出る",
        ),
    ],
)
def test_every_rule_keeps_the_scope(css, why):
    """出力のどの ``{`` も、その前にスコープのクラスを持っていること。

    検証に ``_css_top_level`` を使わない。字句解析そのものを壊したときに、
    壊れた字句解析で見に行くと漏れも見えなくなり、テストが通ってしまう
    （変異テストで実際にそうなった）。ここでは素の文字列操作だけで見る。
    """
    w = ui.html("<b>x</b>", css=css)
    out = w.extra_css()
    for chunk in out.split("}"):
        if "{" not in chunk:
            continue
        selector = chunk.rsplit("{", 1)[0]
        if selector.lstrip().startswith("@"):
            continue
        assert w.scope_class in selector, f"{why}（外に出た: {selector.strip()[:40]}）"


@pytest.mark.parametrize(
    ("css", "keep"),
    [
        # url() の中の ' は文字列の始まりではない。昔はここで ValueError になっていた
        (".a { background: url(ken's.png) }", "ken's.png"),
        # 丸括弧の中の ; で宣言を切ると、つなぎ直すときに空白が入って画像が消える
        ("background: url(data:image/gif;base64,R0lGOD)", "image/gif;base64"),
        # 文字列の中の波括弧は正当
        ("[x='a{b'] { color: red }", "a{b"),
        # 文字列の中の & をネスト参照と取り違えると、属性の値が書き換わる
        ('[data-x="a&b"] { color: red }', '[data-x="a&b"]'),
        ('[href="?a&b"] { color: red }', '[href="?a&b"]'),
    ],
)
def test_legitimate_css_survives_scoping(css, keep):
    assert keep in ui.html("<b>x</b>", css=css).extra_css()


def test_vendor_prefixed_keyframes_are_dropped_like_the_plain_one():
    """``@-webkit-keyframes`` も名前をページ全体に定義する。接頭辞で見逃さない。"""
    out = ui.html("<b>x</b>", css="@-webkit-keyframes zz { from { opacity: 0 } }\n.a { color: red }").extra_css()
    assert "keyframes" not in out
    assert ".a { color: red }" in out


def test_deeply_nested_at_rules_say_so_instead_of_crashing():
    """表示のときに素の RecursionError を出さない（ui.html は成功済みなので尚更）。"""
    deep = "@media print {" * 1000 + ".a{color:red}" + "}" * 1000
    with pytest.raises(ValueError, match="入れ子"):
        ui.html("<b>x</b>", css=deep).extra_css()


def test_a_broken_distribution_stays_quiet(monkeypatch):
    """配布情報が壊れていると版が None で返る。意味の通らない警告を出さない。"""
    import importlib.metadata as meta

    from library_hiroba import _core

    monkeypatch.setattr(_core, "_stale_unsaid", [True])
    monkeypatch.setattr(meta, "version", lambda name: None)
    assert _core.stale_module() == ""
    assert "セッションを再起動する" not in ui.card("題", "本文")._repr_html_()


def test_an_unreadable_distribution_does_not_break_the_display(monkeypatch):
    """親切で出している知らせのために、表示そのものを壊してはいけない。"""
    import importlib.metadata as meta

    from library_hiroba import _core

    def boom(name):
        raise ValueError("A distribution name is required.")

    monkeypatch.setattr(_core, "_stale_unsaid", [True])
    monkeypatch.setattr(meta, "version", boom)
    assert "題" in ui.card("題", "本文")._repr_html_()


def test_css_brace_check_ignores_strings_and_comments():
    """セレクタに波括弧が残っていないかの見張りは、文字列の中を数えない。

    ``scope_css()`` はこれを使って「前置きの切り出しに失敗した」ことを捕まえ、
    黙ってページ全体に漏らす代わりに止める。素朴に ``"{" in text`` で見ると
    ``[x='a{b']`` のような正当なセレクタまで止めてしまう。
    """
    from library_hiroba._components import _css_has_brace

    assert _css_has_brace(".a { color: red }") is True
    assert _css_has_brace(".a }") is True
    assert _css_has_brace("[x='a{b']") is False
    assert _css_has_brace('[x="a}b"]') is False
    assert _css_has_brace("/* { */ .a") is False
    assert _css_has_brace(".a\\{b") is False
    assert _css_has_brace(".a .b > .c:hover") is False


# --- ui.sketch()（JavaScript を動かす閉じた箱）-------------------------------


def sketch_frame(widget) -> str:
    """出力から iframe のタグだけ取り出す。"""
    found = re.search(r"<iframe[^>]*>", widget._repr_html_())
    assert found, "iframe が出ていません"
    return found.group(0)


def test_sketch_puts_the_js_in_a_sandboxed_frame():
    """JS は箱の中に入り、出力はサニタイザの検査を通ること。"""
    widget = ui.sketch("<canvas></canvas>", js="window.x = 1")
    rendered = widget._repr_html_()
    assert check_html(rendered) == []
    frame = sketch_frame(widget)
    assert 'sandbox="allow-scripts allow-modals allow-forms"' in frame
    assert "src=" not in frame.replace("srcdoc=", "")
    # JS は srcdoc の中（＝エスケープされた形）にだけある
    assert "window.x = 1" in rendered
    assert "<script" not in rendered.lower()
    assert "&lt;script&gt;" in rendered


def test_sketch_never_grants_same_origin():
    """``allow-same-origin`` を足さないこと。

    閉じた箱の安全は**この一点だけ**で成り立っている。足すと箱は親と同じ
    オリジンになり、実測で止まっていたもの（親の DOM・親の変数・cookie・
    親ページの遷移）が**全部通る**。「JS を動かす」と「親に触らせない」を
    同時に満たしているのはここなので、ここが崩れたら設計から考え直すこと。
    実物の Chromium での確認は tools/check_sketch_browser.py。
    """
    for widget in (
        ui.sketch("x", js="1"),
        ui.sketch("x", js="1", height=500, width="300px"),
        ui.sketch(js="1"),
    ):
        assert "allow-same-origin" not in widget._repr_html_()


def test_the_sandbox_value_matches_the_checker():
    """``sandbox`` の約束を、ライブラリと検査の両方が同じ値で持っていること。

    検査側だけ緩めると、``allow-same-origin`` の入った箱が素通りする。
    片方を直したら必ず両方を直す（DANGEROUS_TAGS と同じ扱い）。
    """
    import sanitize_check

    from library_hiroba._components import SKETCH_SANDBOX

    assert SKETCH_SANDBOX == sanitize_check.SKETCH_SANDBOX


def test_the_checker_catches_a_frame_that_breaks_the_promise():
    """検査そのものが働くこと（素通しなら上のテストは無意味になる）。"""
    assert check_html('<iframe srcdoc="x"></iframe>') != []
    assert check_html('<iframe sandbox="allow-scripts allow-same-origin"></iframe>') != []
    assert check_html('<iframe sandbox="allow-scripts allow-modals allow-forms" src="/x">') != []
    assert check_html('<iframe sandbox="allow-scripts allow-modals allow-forms"></iframe>') == []


def test_sketch_refuses_a_script_end_tag_in_the_js():
    """``</script>`` があると JS が途中で切れる。書いた時点で止める。

    HTML のパーサは文字列の中の ``</script>`` も見分けない。実測では
    「Invalid or unexpected token」になり、箱の中は真っ白なまま理由が出ない。
    """
    with pytest.raises(ValueError, match="</script>"):
        ui.sketch(js='const s = "</script>"')
    with pytest.raises(ValueError, match="</script>"):
        ui.sketch(js="x = '</ SCRIPT >'")
    # 逃がしてあるものは通る
    assert ui.sketch(js='const s = "<\\/script>"')._repr_html_()


def test_sketch_neutralises_a_style_end_tag_in_the_css():
    """箱の中の ``<style>`` も ``</style>`` で終わってしまうので、無害化する。"""
    widget = ui.sketch("x", css="body { color: red } /* </style><b>は */")
    assert "</style><b>" not in widget.document()
    assert "<\\/style" in widget.document()


def test_sketch_hands_the_box_to_the_host_in_pyhiroba(monkeypatch):
    """PyHiroba では iframe を出さず、中身を ``data-hui-sketch`` で渡すこと。

    iframe をそのまま出すと本体のサニタイザが消す。``srcdoc`` は値の中の
    ``</script`` を見て落とされ、フックでも残せない（その検査がフックより
    手前にある）。``data-*`` 属性は**設定を変えなくても残る**ので、base64 に
    してそこへ載せ、iframe は本体の JS に組んでもらう。
    """
    from library_hiroba import _components

    monkeypatch.setattr(_components, "in_browser", lambda: True)
    monkeypatch.setattr(_components, "host_supports", lambda feature: feature == "sketch")
    widget = ui.sketch("<canvas></canvas>", js="window.x = 1")
    shown = widget._repr_html_()
    assert check_html(shown) == []
    assert "<iframe" not in shown
    assert f'data-hui-sketch="{widget.packed()}"' in shown
    # base64 なので、落とされる形（</script や --> ）が値に出ない
    packed = re.search(r'data-hui-sketch="([^"]*)"', shown).group(1)
    assert re.fullmatch(r"[A-Za-z0-9+/=]+", packed), packed
    # 往復すること
    import base64

    assert base64.b64decode(packed).decode("utf-8") == widget.document()
    assert "window.x = 1" in widget.document()


def test_sketch_says_so_where_it_cannot_work(monkeypatch):
    """対応していない本体では、黙って消えずに理由を出すこと。

    iframe は本体のサニタイザで取り除かれる。何も出さないと「Colab では
    動いたのに PyHiroba では無反応」になり、原因がどこにも出ない。
    """
    from library_hiroba import _components

    # 未対応の PyHiroba
    monkeypatch.setattr(_components, "in_browser", lambda: True)
    monkeypatch.setattr(_components, "host_supports", lambda feature: False)
    shown = ui.sketch("x", js="1")._repr_html_()
    assert "<iframe" not in shown
    assert "hui-alert-warning" in shown
    assert "ui.sketch" in shown
    # 注意書きの見た目に要る CSS も一緒に出ていること（入れ忘れると素の文字になる）
    assert ".hui-alert{" in shown

    # 対応済みの本体。ここに注意書きを出してはいけない
    monkeypatch.setattr(_components, "host_supports", lambda feature: feature == "sketch")
    shown = ui.sketch("x", js="1")._repr_html_()
    assert "data-hui-sketch=" in shown
    assert "hui-alert" not in shown


def test_sketch_size_takes_a_number_or_a_length():
    assert "height: 300px" in ui.sketch("x", height=300).extra_css()
    assert "height: 50vh" in ui.sketch("x", height="50vh").extra_css()
    assert "width: 320px" in ui.sketch("x", width=320).extra_css()
    # 幅を指定しなければ、幅の指定は出さない（部品側の 100% が効く）
    assert "width" not in ui.sketch("x").extra_css()


@pytest.mark.parametrize(
    "attack",
    [
        "0;position:fixed;top:0;left:0;width:100vw;height:100vh",
        "240px;background:url(https://evil.example/x)",
        "240px}.hui{display:none",
        "expression(alert(1))",
    ],
)
def test_sketch_size_cannot_carry_extra_css(attack):
    """高さは CSS にそのまま入るので、長さ以外は受け付けないこと。"""
    with pytest.raises(ValueError, match=r"長さ|高さ"):
        ui.sketch("x", height=attack)


def test_sketch_cannot_break_out_of_the_srcdoc_attribute():
    """箱の中身は属性値に入る。引用符で属性を割って外に出られないこと。"""
    widget = ui.sketch('<b title="x">" onload="alert(1)</b>', js='alert("\'")')
    rendered = widget._repr_html_()
    assert check_html(rendered) == []
    # 生の " は srcdoc の中に出さない（出ると属性がそこで終わる）
    srcdoc = re.search(r'srcdoc="([^"]*)"', rendered)
    assert srcdoc, "srcdoc が属性として取り出せません"
    assert "onload" not in sketch_frame(widget).replace(srcdoc.group(1), "")


def test_sketch_does_not_fetch_anything_by_default():
    """箱の中も、既定では外に取りに行かないこと（土台の CSS と同じ約束）。"""
    assert "googleapis" not in ui.sketch("x", js="1").document()


def test_ui_html_still_refuses_an_iframe_written_by_hand():
    """``ui.sketch()`` を足しても、``ui.html()`` の iframe は断ったままにする。

    sketch は sandbox を自分で付けるから通している。手書きの iframe は
    何が付くか分からないうえ、本体のサニタイザが取り除く。
    """
    assert dangerous_html('<iframe sandbox="allow-scripts"></iframe>') != []
    with pytest.raises(ValueError, match="iframe"):
        ui.html('<iframe sandbox="allow-scripts" srcdoc="x"></iframe>')
