"""10個の UI 部品と、それを生成する小文字のファクトリ関数。

すべての部品はテキスト引数を HTML エスケープする。エスケープしない唯一の
経路は :func:`html`（明示的な逃げ道）だけ。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from html.parser import HTMLParser
from typing import ClassVar, Union

from ._core import (
    Container,
    HasValues,
    Item,
    Stack,
    Widget,
    as_items,
    as_number,
    css_length,
    esc,
    esc_attr,
    shown,
    unique_name,
    value_html,
)

Number = Union[int, float]


class Card(HasValues):
    css_keys = ("card",)

    def __init__(
        self,
        title: object,
        body: object = "",
        icon: str | None = None,
        footer: object = None,
    ):
        self.title = title
        self.body = body
        self.icon = icon
        self.footer = footer

    def value_slots(self) -> list[object]:
        return [self.title, self.body, self.icon, self.footer]

    def fragment(self) -> str:
        parts = []
        if shown(self.title):
            icon = (
                f'<span class="hui-card-icon">{value_html(self.icon)}</span>' if shown(self.icon) else ""
            )
            parts.append(f'<div class="hui-card-title">{icon}<span>{value_html(self.title)}</span></div>')
        if shown(self.body):
            parts.append(f'<div class="hui-card-body">{value_html(self.body)}</div>')
        if self.footer is not None:
            parts.append(f'<div class="hui-card-footer">{value_html(self.footer)}</div>')
        return f'<div class="hui-card">{"".join(parts)}</div>'


class Alert(HasValues):
    css_keys = ("alert",)

    # PyHiroba に合わせ絵文字は使わず、CSS の円形マーク内に文字記号を置く
    MARKS: ClassVar[dict[str, str]] = {
        "info": "i",
        "success": "✓",
        "warning": "!",
        "danger": "×",
    }
    # 記号は目で見るためのもの（aria-hidden）。読み上げには言葉で種類を伝える
    SPOKEN: ClassVar[dict[str, str]] = {
        "info": "お知らせ",
        "success": "できました",
        "warning": "注意",
        "danger": "警告",
    }

    def __init__(self, message: object, kind: str = "info", title: object = None):
        if kind not in self.MARKS:
            raise ValueError(
                f"kind は {sorted(self.MARKS)} のいずれかにしてください（指定値: {kind!r}）"
            )
        self.message = message
        self.kind = kind
        self.title = title

    def value_slots(self) -> list[object]:
        return [self.message, self.title]

    def fragment(self) -> str:
        kind_class = "" if self.kind == "info" else f" hui-alert-{self.kind}"
        title = (
            f'<div class="hui-alert-title">{value_html(self.title)}</div>' if shown(self.title) else ""
        )
        return (
            f'<div class="hui-alert{kind_class}">'
            f'<span class="hui-alert-icon" aria-hidden="true">{self.MARKS[self.kind]}</span>'
            f'<span class="hui-vh">{self.SPOKEN[self.kind]}：</span>'
            f"<div>{title}<div>{value_html(self.message)}</div></div>"
            f"</div>"
        )


class Quiz(Widget):
    css_keys = ("quiz",)

    def __init__(
        self,
        question: object,
        choices: Sequence[object],
        answer: object,
        explanation: object = None,
        correct_text: str = "✓ 正解！",
        incorrect_text: str = "× ざんねん…",
    ):
        choice_list = [str(c) for c in choices]
        if len(choice_list) < 2:
            raise ValueError("choices は2つ以上にしてください")
        if len(set(choice_list)) != len(choice_list):
            raise ValueError(f"choices に重複があります: {choice_list!r}")
        answer_str = str(answer)
        if answer_str not in choice_list:
            raise ValueError(f"answer {answer!r} が choices {choice_list!r} の中にありません")
        self.question = question
        self.choices = choice_list
        self.answer = answer_str
        self.explanation = explanation
        self.correct_text = correct_text
        self.incorrect_text = incorrect_text
        # PyHiroba では全セルが 1 document を共有するため name は一意にする
        self.name = unique_name("hui-quiz")
        if explanation is not None:
            self.css_keys = ("quiz", "reveal")

    def fragment(self) -> str:
        rows = []
        for choice in self.choices:
            is_answer = choice == self.answer
            cls = "hui-choice hui-is-answer" if is_answer else "hui-choice"
            feedback = self.correct_text if is_answer else self.incorrect_text
            rows.append(
                f'<label class="{cls}">'
                f'<input type="radio" name="{esc_attr(self.name)}">'
                f'<span class="hui-choice-text">{esc(choice)}</span>'
                f'<span class="hui-fb">{esc(feedback)}</span>'
                f"</label>"
            )
        explanation = ""
        if self.explanation is not None:
            explanation = (
                '<details class="hui-reveal hui-quiz-exp"><summary>解説を見る</summary>'
                f'<div class="hui-reveal-body">{esc(self.explanation)}</div></details>'
            )
        return (
            f'<div class="hui-quiz"><div class="hui-quiz-q">{esc(self.question)}</div>'
            f'{"".join(rows)}{explanation}</div>'
        )


class Reveal(HasValues):
    css_keys = ("reveal",)

    def __init__(self, content: object, summary: object = "答えを見る"):
        self.content = content
        self.summary = summary

    def value_slots(self) -> list[object]:
        return [self.content, self.summary]

    def fragment(self) -> str:
        return (
            f'<details class="hui-reveal"><summary>{value_html(self.summary)}</summary>'
            f'<div class="hui-reveal-body">{value_html(self.content)}</div></details>'
        )


class Progress(Widget):
    css_keys = ("progress",)

    def __init__(
        self,
        value: Number,
        max: Number = 100,
        label: object = None,
        show_value: bool = True,
    ):
        max_value = as_number(max, "max")
        if max_value <= 0:
            raise ValueError(f"max は正の数にしてください（指定値: {max!r}）")
        self.value = as_number(value, "value")
        self.max = max_value
        self.label = label
        self.show_value = show_value

    @property
    def percent(self) -> float:
        return min(100.0, max(0.0, self.value / self.max * 100.0))

    def fragment(self) -> str:
        percent_text = f"{self.percent:.0f}%"
        head = ""
        if self.label is not None or self.show_value:
            label = f"<span>{esc(self.label)}</span>" if self.label is not None else "<span></span>"
            num = f'<span class="hui-progress-num">{percent_text}</span>' if self.show_value else ""
            head = f'<div class="hui-progress-head">{label}{num}</div>'
        aria_label = esc_attr(self.label if self.label is not None else "進捗")
        return (
            f'<div class="hui-progress">{head}'
            f'<div class="hui-progress-track" role="progressbar" aria-label="{aria_label}"'
            f' aria-valuemin="0" aria-valuemax="100" aria-valuenow="{self.percent:.0f}">'
            f'<div class="hui-progress-fill" style="width: {self.percent:.4g}%;"></div>'
            f"</div></div>"
        )


class Stat(HasValues):
    css_keys = ("stat",)

    def __init__(
        self,
        label: object,
        value: object,
        unit: object = None,
        icon: str | None = None,
    ):
        self.label = label
        self.value = value
        self.unit = unit
        self.icon = icon

    def value_slots(self) -> list[object]:
        return [self.label, self.value, self.unit, self.icon]

    def fragment(self) -> str:
        icon = f"{value_html(self.icon)} " if shown(self.icon) else ""
        unit = (
            f'<span class="hui-stat-unit">{value_html(self.unit)}</span>' if shown(self.unit) else ""
        )
        return (
            f'<div class="hui-stat">'
            f'<span class="hui-stat-label">{icon}{value_html(self.label)}</span>'
            f'<span class="hui-stat-value">{value_html(self.value)}{unit}</span>'
            f"</div>"
        )


class Columns(Container):
    css_keys = ("columns",)

    def __init__(
        self,
        items: Sequence[Item],
        widths: Sequence[Number] | None = None,
        gap: str = "12px",
    ):
        super().__init__(items)
        if widths is not None:
            widths = [as_number(w, "widths") for w in widths]
            if len(widths) != len(self.children):
                raise ValueError(
                    f"widths の数（{len(widths)}）を部品の数（{len(self.children)}）に合わせてください"
                )
            if any(w <= 0 for w in widths):
                raise ValueError(f"widths は正の数にしてください（指定値: {widths!r}）")
        self.widths = widths
        self.gap = css_length(gap, "gap")

    def fragment(self) -> str:
        cols = []
        for i, child in enumerate(self.children):
            style = f' style="flex: {self.widths[i]:.4g} 1 0;"' if self.widths else ""
            cols.append(f'<div class="hui-col"{style}>{child.fragment()}</div>')
        return f'<div class="hui-cols" style="gap: {self.gap};">{"".join(cols)}</div>'


class Badge(HasValues):
    css_keys = ("badge",)

    COLORS = ("blue", "green", "red", "amber", "gray")

    def __init__(self, text: object, color: str = "blue"):
        if color not in self.COLORS:
            raise ValueError(
                f"color は {list(self.COLORS)} のいずれかにしてください（指定値: {color!r}）"
            )
        self.text = text
        self.color = color

    def value_slots(self) -> list[object]:
        return [self.text]

    def fragment(self) -> str:
        color_class = "" if self.color == "gray" else f" hui-badge-{self.color}"
        return f'<span class="hui-badge{color_class}">{value_html(self.text)}</span>'


# 1行1辞書のとき、キーがそのまま列名になる。行ごとにキーが違う書き方
# （``[{語: 意味} for 語, 意味 in ペア]`` のような単語帳）をすると、列が行数ぶん
# 生えてセルが行数の2乗になる。例外も警告も出ないまま、1000行で100万セル・
# 4000行で約140MB の HTML になり、GIGA 端末（3〜4GB）は描画で固まる。
# 教室で読める表の列数からは十分に離してあるので、超えたら書き方の間違いとして止める。
MAX_TABLE_COLUMNS = 200


class Table(Widget):
    css_keys = ("table",)

    def __init__(
        self,
        data: Sequence[object],
        headers: Sequence[object] | None = None,
        caption: object = None,
    ):
        if isinstance(data, dict):
            raise ValueError(
                "data には行の一覧を渡してください。1行だけのときも "
                'ui.table([{"名前": "佐藤"}]) のようにリストで囲みます。'
            )
        rows = list(data)
        # headers は下で何度もなぞる。生成器のまま受け取ると最初の1行で尽きて、
        # 2行目以降が黙って空欄になる（表示は出るので気付けない）。先に確定させる。
        if isinstance(headers, str):
            # list("名前") は ['名','前'] になる。列が1文字ずつに割れ、辞書の行は
            # どのキーにも一致しないので**中身が空欄のまま**表が出る。例外にならない
            raise ValueError(
                f"headers には列名のリストを渡してください（指定値: {headers!r}）。"
                f'文字列をそのまま渡すと1文字ずつ別の列になります（1列なら ["{headers}"]）。'
            )
        if headers is not None:
            headers = list(headers)
        if not rows:
            raise ValueError("data が空です")

        dict_rows = sum(isinstance(r, dict) for r in rows)
        if dict_rows not in (0, len(rows)):
            raise ValueError(
                "行の形が混ざっています。すべて辞書にするか、すべてリストにしてください。"
            )
        if dict_rows == 0 and any(isinstance(r, str) for r in rows):
            raise ValueError(
                "行が文字列になっています。1行は値の一覧です（例: [[1, 2], [3, 4]]）。"
            )
        # 1行は「値の一覧」。数値をそのまま並べると 'int' object is not iterable と
        # いう英語だけが出て、どこが悪いのか分からない
        if dict_rows == 0:
            flat = [r for r in rows if not isinstance(r, (list, tuple))]
            if flat:
                raise ValueError(
                    f"行が値そのものになっています（指定値: {flat[0]!r}）。"
                    "1行は値の一覧です。1列なら [[90], [85]] のように包んでください。"
                )

        if dict_rows:
            if headers is None:
                # 行をまたいでキーを集める（任意の項目が欠けている行は空欄で並ぶ）。
                # dict は入れた順を保つので、出てきた順がそのまま列の順になる
                collected: dict[object, None] = {}
                for r in rows:
                    for key in r:
                        collected[key] = None
                headers = list(collected)
                if len(headers) > MAX_TABLE_COLUMNS:
                    raise ValueError(
                        f"列が {len(headers)} 個になりました（行は {len(rows)} 行）。"
                        "1行1辞書のときは、辞書のキーが列名になります。"
                        "行ごとに違うキーを使うと、列が行数ぶん増えて表が開かなくなります。"
                        "「名前と値を2列で並べたい」のであれば "
                        "[[キー, 値] for キー, 値 in もとの辞書.items()] のように"
                        "1行を値の一覧にしてください。"
                    )
            self.rows = [[r.get(h, "") for h in headers] for r in rows]
        else:
            self.rows = [list(r) for r in rows]

        self.headers = list(headers) if headers is not None else None
        # 列数の足りない行は空欄で埋める（欠けたまま出すと列がずれる）
        width = max([len(r) for r in self.rows] + [len(self.headers or [])])
        for row in self.rows:
            row.extend([""] * (width - len(row)))
        self.caption = caption

    def fragment(self) -> str:
        caption = f"<caption>{esc(self.caption)}</caption>" if self.caption is not None else ""
        thead = ""
        if self.headers is not None:
            cells = "".join(f'<th scope="col">{esc(h)}</th>' for h in self.headers)
            thead = f"<thead><tr>{cells}</tr></thead>"
        body_rows = "".join(
            "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>"
            for row in self.rows
        )
        return (
            f'<div class="hui-table-wrap"><table class="hui-table">{caption}'
            f"{thead}<tbody>{body_rows}</tbody></table></div>"
        )


# CSS 文字列中の "</style" で <style> ブロックが早期終了しないよう無害化する
_STYLE_CLOSE_RE = re.compile(r"</style", re.IGNORECASE)


def _css_skip(css: str, i: int) -> int | None:
    """``css[i]`` から始まるコメントか文字列を読み飛ばし、その次の位置を返す。

    どちらでもなければ ``None``。

    **CSS では生の改行で文字列が終わる**（仕様の bad-string-token）。ここを
    見落として「引用符が閉じるまで中身」と読むと、文字列の中だと思い込んだ ``}``
    をブラウザは本物として読み、スコープの外へ CSS が漏れる。下の括弧の検査と
    ``scope_css()`` の両方がこの関数を使うので、食い違いが生まれない。
    """
    if css.startswith("/*", i):
        end = css.find("*/", i + 2)
        return len(css) if end == -1 else end + 2
    quote = css[i]
    if quote not in "\"'":
        return None
    j, n = i + 1, len(css)
    while j < n:
        ch = css[j]
        if ch == "\\":
            # 行末の \ は改行を打ち消して文字列を続ける（\r\n はひとつ分）
            j += 3 if css.startswith("\r\n", j + 1) else 2
            continue
        if ch in "\n\r\f":
            return j  # 文字列はここで切れる。改行は呼び出し側が読み直す
        if ch == quote:
            return j + 1
        j += 1
    return n


def css_stays_inside_scope(css: str) -> bool:
    """波括弧の対応が取れていて、スコープの外に出ていないかを調べる。

    ``scoped=True`` の CSS は ``.一意なクラス`` の中だけに効くよう書き換えるが、
    途中に余分な ``}`` があるとそこでスコープが切れ、以降がページ全体に効く。
    文字列とコメントの中の括弧は数えない。
    """
    depth = 0
    i, n = 0, len(css)
    while i < n:
        skipped = _css_skip(css, i)
        if skipped is not None:
            i = skipped
            continue
        ch = css[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0


# スコープの中に閉じ込められない at-rule。落とす。
#
# ``@keyframes`` や ``@font-face`` は「名前」をページ全体に定義するもので、
# スコープの内側という概念がない。CSS ネストで包んでいたときはネストの中では
# 無効だったため黙って捨てられていた。前置方式ではトップレベルへ出せてしまうが、
# それをすると名前がページ全体で共有になり、全セルが1つの document を共有する
# PyHiroba では別のセルのアニメーションと取り違えが起きる。
# ``notebooks/html_css_recipes.ipynb`` が「これらは scoped=False で書く」と
# 教えているので、そちらに揃えてここでは落とす（従来と同じ挙動）。
_AT_UNSCOPABLE = frozenset(
    {
        "import",
        "charset",
        "namespace",
        "keyframes",
        "font-face",
        "property",
        "counter-style",
        "font-feature-values",
    }
)
# 中身が普通のルールなので、前置しながら中へ降りる at-rule
_AT_NESTING = frozenset({"media", "supports", "container", "layer", "scope"})
_AT_NAME_RE = re.compile(r"@([-\w]+)")


def _css_top_level(css: str) -> list[tuple[str, str | None]]:
    """CSS を ``(前置き, 中身)`` の並びに切る。``;`` で終わるものの中身は ``None``。"""
    items: list[tuple[str, str | None]] = []
    start = 0
    i, n = 0, len(css)
    while i < n:
        skipped = _css_skip(css, i)
        if skipped is not None:
            i = skipped
            continue
        ch = css[i]
        if ch == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                inner = _css_skip(css, j)
                if inner is not None:
                    j = inner
                    continue
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            items.append((css[start:i], css[i + 1 : j - 1 if depth == 0 else j]))
            i = start = j
            continue
        if ch == ";":
            items.append((css[start : i + 1], None))
            i += 1
            start = i
            continue
        i += 1
    tail = css[start:].strip()
    if tail:
        items.append((tail, None))
    return items


def _css_split_commas(text: str) -> list[str]:
    """``:is(a, b)`` や ``[x="a,b"]`` の中のカンマでは切らずにセレクタを分ける。"""
    parts: list[str] = []
    start = depth = 0
    i, n = 0, len(text)
    while i < n:
        skipped = _css_skip(text, i)
        if skipped is not None:
            i = skipped
            continue
        ch = text[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


def _css_strip_comments(text: str) -> str:
    """コメントだけを落とす（文字列の中は触らない）。

    前置きの判定に使う。残したままだと、セレクタの前のコメントがセレクタに
    混ざり、末尾のコメントが「セレクタの無い宣言」と見なされて空のルールが出る。
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        skipped = _css_skip(text, i)
        if skipped is not None:
            out.append(text[i:skipped])
            i = skipped
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def scope_css(css: str, scope: str) -> str:
    """ユーザー CSS を ``scope`` の中だけに効くよう、セレクタに前置して書き換える。

    ``scope { ... }`` で包む（CSS ネスト）だけでは、ネスト未対応のブラウザで
    中身が丸ごと捨てられ、**ユーザー CSS が1行も効かない**。GIGA 端末には
    iPadOS 15〜16.3（Safari 16.5 未満）が実際に残っており、そこでは教材の
    棒グラフも吹き出しも素のテキストに落ちる。しかも何のエラーも出ない。
    セレクタに直接前置すれば、どのブラウザでも同じように効く。

    効き方（詳細度も含めて）はネスト版と同じになるようにしてある。
    ``:is(.scope) sel`` と ``.scope sel`` は、クラス1つなら同じ詳細度。
    """
    rules: list[str] = []
    loose: list[str] = []  # セレクタの無い宣言。scope 自身に当てる
    for prelude, body in _css_top_level(css):
        text = _css_strip_comments(prelude).strip()
        if not text:
            # 前置きがコメントだけ。中身があるなら scope 自身に当てる
            if body is not None and body.strip():
                rules.append(f"{scope} {{{body}}}")
            continue
        if text.startswith("@"):
            found = _AT_NAME_RE.match(text)
            name = found.group(1).lower() if found else ""
            if name in _AT_UNSCOPABLE:
                continue
            if body is None:
                rules.append(text if text.endswith(";") else text + ";")
            elif name in _AT_NESTING:
                inner = scope_css(body, scope)
                if inner.strip():
                    rules.append(f"{text} {{\n{inner}\n}}")
            else:
                # @keyframes や @font-face の中はセレクタではないので触らない
                rules.append(f"{text} {{{body}}}")
            continue
        if body is None:
            loose.append(text if text.endswith(";") else text + ";")
            continue
        selectors = ", ".join(
            part.strip().replace("&", scope) if "&" in part else f"{scope} {part.strip()}"
            for part in _css_split_commas(text)
            if part.strip()
        )
        rules.append(f"{selectors} {{{body}}}" if selectors else f"{scope} {{{body}}}")
    if loose:
        rules.insert(0, f"{scope} {{\n{' '.join(loose)}\n}}")
    return "\n".join(rules)


# PyHiroba は表示の直前に本体側のサニタイザ（DOMPurify）を通すため、ここに並べた
# ものは出力から消える。Colab にはそのサニタイザが無いので、書いた本人は Colab で
# 動くのを見て「できた」と思い、PyHiroba に載せて初めて消えているのに気付く。
# それを避けるため、書いた時点で止める。
#
# tests/sanitize_check.py に同じ一覧がある。片方から import すると検査の正しさを
# テスト自身が保証できなくなるので、あえて分けたうえで、両者が一致することを
# test_components.py で確かめている。増やすときは両方を直す。
DANGEROUS_TAGS = frozenset(
    {
        "script",
        "iframe",
        "frame",
        "frameset",
        "form",
        "object",
        "embed",
        "applet",
        "link",
        "meta",
        "base",
    }
)

# 値に javascript: が書ける属性
URL_ATTRS = frozenset({"href", "src", "action", "formaction", "xlink:href", "data"})

# ``<!-->`` と ``<!--->`` は HTML では「中身の無いコメント」としてその場で閉じる
# （HTML 仕様の abrupt-closing-of-empty-comment）。ところが Python の HTMLParser は
# ``-->`` が来るまでコメントが続くと見るため、後ろのタグを全部コメント本文として
# 飲み込む。その食い違いを突かれると、``<!--><img src=x onerror=…>-->`` が下の検査に
# 一つも引っかからないまま通り、Colab（サニタイザが無い）で実際に動いてしまう。
# 見る前に、両者が同じ意味に読む ``<!---->`` へ直しておく。
#
# ブラウザとの食い違いは tools/check_parser_parity.py で一覧を突き合わせて確かめた。
# すり抜けるのはこの2つだけで、``--!>`` や ``<![CDATA[`` や ``<?php`` は
# HTMLParser 側でも検知できている。
_EMPTY_COMMENT_RE = re.compile(r"<!---?>")


class _DangerFinder(HTMLParser):
    """``ui.html()`` に渡された HTML から、PyHiroba 側で消えるものを拾う。

    正規表現ではなく HTMLParser を使うのは、属性値の実体参照が復元された状態で
    渡ってくるため。``&#106;avascript:`` のような書き方を自前で戻さずに済む。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        # <embed/> のような書き方は HTMLParser が既定でここへ回してくれる
        if tag in DANGEROUS_TAGS:
            self.found.append(f"<{tag}> タグ")
        for name, value in attrs:
            lowered = name.lower()
            if lowered.startswith("on"):
                self.found.append(f"<{tag}> の {name} 属性")
            elif lowered in URL_ATTRS and value is not None:
                # java\nscript: のように途中に空白を挟んでも URL としては通るため、
                # 空白を落としてから見る
                if "".join(value.split()).lower().startswith("javascript:"):
                    self.found.append(f"<{tag}> の {name}=\"javascript:...\"")


def dangerous_html(raw: str) -> list[str]:
    """PyHiroba 側で取り除かれる要素を探し、見つかったものを並べて返す。

    空リストなら、Colab と PyHiroba で同じ表示になる。``id`` や ``style`` は
    どちらの環境でも残るので、ここでは見ない。
    """
    finder = _DangerFinder()
    finder.feed(_EMPTY_COMMENT_RE.sub("<!---->", raw))
    finder.close()
    # 同じものが何度も出てきても、伝えたいことは1回で足りる
    return list(dict.fromkeys(finder.found))


class RawHtml(Widget):
    css_keys = ()

    def __init__(self, raw: object, css: str | None = None, scoped: bool = True):
        self.raw = str(raw)
        found = dangerous_html(self.raw)
        if found:
            raise ValueError(
                "ui.html() に、PyHiroba では表示できないものが含まれています: "
                + "、".join(found)
                + "。PyHiroba は表示の直前にこれらを取り除くため、Colab で動いても"
                "本番では動きません。両方で同じ表示になるように書き直してください。"
                "（Colab だけで試すなら IPython.display.HTML が使えます）"
            )
        if css is not None and scoped and not css_stays_inside_scope(str(css)):
            raise ValueError(
                "CSS の波括弧 { } の数が合っていません。閉じ忘れか、余分な } があります。"
                "そのままだと CSS がこの部品の外に出て、ページ全体の見た目を変えてしまいます。"
                "意図してページ全体に効かせたい場合は scoped=False を指定してください。"
            )
        self.css = None if css is None else _STYLE_CLOSE_RE.sub(lambda _: "<\\/style", str(css))
        # scoped の場合はインスタンスごとに一意なクラスで CSS の効く範囲を限定する
        # （PyHiroba では全セルが 1 document を共有するため、ページや他セルを汚さない）
        self.scope_class = unique_name("hui-raw") if (self.css is not None and scoped) else None

    def extra_css(self) -> str:
        if self.css is None:
            return ""
        if self.scope_class is not None:
            # セレクタに前置してスコープする。CSS ネストで包むと、ネスト未対応の
            # 端末（iPadOS 15〜16.3 など）で中身が丸ごと捨てられて何も効かない
            return scope_css(self.css, f".{self.scope_class}")
        return self.css

    def fragment(self) -> str:
        cls = "hui-raw" if self.scope_class is None else f"hui-raw {self.scope_class}"
        return f'<div class="{cls}">{self.raw}</div>'


# ---------------------------------------------------------------------------
# 公開 API（ファクトリ関数）
# ---------------------------------------------------------------------------


def card(title, body="", icon=None, footer=None) -> Card:
    """説明カード。

    >>> ui.card("今日の目標", "for文を使って、九九の表を作ってみよう！")
    """
    return Card(title, body=body, icon=icon, footer=footer)


def alert(message, kind="info", title=None) -> Alert:
    """ヒント・注意の表示。kind は info / success / warning / danger。

    >>> ui.alert("range(5) は 0 から 4 までだよ", kind="warning")
    """
    return Alert(message, kind=kind, title=title)


def quiz(
    question,
    choices,
    answer,
    explanation=None,
    correct_text="✓ 正解！",
    incorrect_text="× ざんねん…",
) -> Quiz:
    """選択式クイズ。選ぶと CSS だけで正誤が色とマークで表示される。

    ``answer`` は選択肢の値そのもので指定する（インデックスではない）。

    >>> ui.quiz("2の8乗は？", choices=[128, 256, 512], answer=256, explanation="2×2を8回！")
    """
    return Quiz(
        question,
        choices,
        answer,
        explanation=explanation,
        correct_text=correct_text,
        incorrect_text=incorrect_text,
    )


def reveal(content, summary="答えを見る") -> Reveal:
    """クリックで開閉する「答え・解説」ボックス。

    >>> ui.reveal("答えは 42 です", summary="答えを見る")
    """
    return Reveal(content, summary=summary)


def progress(value, max=100, label=None, show_value=True) -> Progress:
    """進捗バー。0〜100% にクランプされる。

    >>> ui.progress(7, max=10, label="練習問題")
    """
    return Progress(value, max=max, label=label, show_value=show_value)


def stat(label, value, unit=None, icon=None) -> Stat:
    """数値の強調表示タイル。

    >>> ui.stat("正答率", 85, unit="%")
    """
    return Stat(label, value, unit=unit, icon=icon)


def columns(*items, widths=None, gap="12px") -> Columns:
    """部品を横並びに配置する。狭い画面では自動で折り返す。

    >>> ui.columns(ui.stat("得点", 90), ui.stat("順位", 3))
    """
    return Columns(as_items(items), widths=widths, gap=gap)


def badge(text, color="blue") -> Badge:
    """ラベル表示用のバッジ。color は blue / green / red / amber / gray。

    >>> ui.badge("重要", color="red")
    """
    return Badge(text, color=color)


def table(data, headers=None, caption=None) -> Table:
    """整形テーブル。dict のリスト（ヘッダ自動）か、リストのリスト + headers。

    >>> ui.table([{"名前": "佐藤", "得点": 90}, {"名前": "鈴木", "得点": 85}])
    """
    return Table(data, headers=headers, caption=caption)


def html(raw, css=None, scoped=True) -> RawHtml:
    """HTML をエスケープせずそのまま表示する（明示的な逃げ道）。CSS も書ける。

    >>> ui.html('<div class="fukidashi">こんにちは！</div>',
    ...         css=".fukidashi { border: 2px solid pink; border-radius: 16px; }")

    - ``css``: この部品と一緒に出力される自由な CSS。
    - ``scoped=True``（既定）: CSS はこの部品の範囲だけに効く（インスタンスごとの
      一意なクラスと CSS ネストで自動スコープ）。ページや他のセルを汚さない。
    - ``scoped=False``: CSS をそのまま出力する。Colab では出力 iframe 内、
      PyHiroba では**ページ全体**に効く点に注意。``@keyframes`` などトップレベル
      専用の @ルールを使う場合はこちらを指定する。

    渡した内容はエスケープされずそのまま出力に含まれるため、信頼できる内容にだけ
    使うこと。ただし PyHiroba 側で消えてしまうもの — ``<script>`` ``<iframe>``
    ``<form>`` などのタグ、``onclick`` のようなイベント属性、``javascript:`` の
    URL — は、書いた時点で ``ValueError`` になる。Colab では動くのに PyHiroba では
    動かない、という食い違いを防ぐため。``id`` や ``style`` は自由に書ける。
    """
    return RawHtml(raw, css=css, scoped=scoped)


def stack(*items, gap="12px") -> Stack:
    """複数の部品を縦に積んで 1 つの表示にまとめる。

    >>> ui.stack(ui.card("目標", "..."), ui.progress(3, max=10))
    """
    return Stack(as_items(items), gap=gap)


class Thinking(HasValues):
    """「考え中」を点の動きで伝える部品。

    答えが出るまで画面が変わらないと、押せていないと思われる。JavaScript は
    使えないので、点の明滅は CSS だけで動かしている。
    """

    css_keys = ("thinking",)

    def __init__(self, text: object = "考え中"):
        self.text = text

    def value_slots(self) -> list[object]:
        return [self.text]

    def fragment(self) -> str:
        label = f"<span>{value_html(self.text)}</span>" if shown(self.text) else ""
        # 点は目で見るためのもの。読み上げには言葉だけ伝える
        return (
            f'<div class="hui-thinking" role="status">{label}'
            f'<span class="hui-thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span>'
            f"</div>"
        )


def thinking(text="考え中") -> Thinking:
    """答えを待っていることを、点の動きで伝える。

    >>> ui.thinking("AI が考えています")

    ``ui.form()`` は送信の直後にこれを自動で出す（``pending`` で変えられる）。
    """
    return Thinking(text)


class Chat(Container):
    """会話を吹き出しで並べる部品。"""

    css_keys = ("chat",)

    ROLES = ("user", "assistant", "note")
    DEFAULT_NAMES: ClassVar[dict[str, str]] = {"user": "あなた", "assistant": "AI", "note": ""}

    def __init__(self, messages: Sequence[object], names: dict | None = None):
        rows = []
        for message in messages:
            if isinstance(message, dict):
                role, content = message.get("role", "assistant"), message.get("content", "")
            else:
                role, content = message
            role = str(role)
            if role not in self.ROLES:
                raise ValueError(
                    f"role は {list(self.ROLES)} のいずれかにしてください（指定値: {role!r}）"
                )
            rows.append((role, content))
        if not rows:
            raise ValueError("メッセージを1つ以上渡してください")
        # 中身が部品なら CSS をまとめるため、コンテナの子として扱う
        super().__init__([content for _role, content in rows])
        self.roles = [role for role, _content in rows]
        self.names = {**self.DEFAULT_NAMES, **(names or {})}

    def fragment(self) -> str:
        rows = []
        for role, child in zip(self.roles, self.children):
            name = self.names.get(role, "")
            label = f'<span class="hui-msg-name">{esc(name)}</span>' if name else ""
            rows.append(
                f'<div class="hui-msg hui-msg-{role}">{label}'
                f'<div class="hui-msg-body">{child.fragment()}</div></div>'
            )
        return f'<div class="hui-chat">{"".join(rows)}</div>'


class Conversation(Widget):
    """会話をためておいて、吹き出しで表示する部品。

    :class:`Chat` は渡された分をその場で描くだけなので、往復するたびに
    ``{"role": ..., "content": ...}`` の辞書を自分で組み立てて持ち回ることになる。
    こちらは足していける入れ物で、表示は ``Chat`` に任せる。
    """

    css_keys = Chat.css_keys

    def __init__(self, messages: Sequence[object] | None = None, names: dict | None = None):
        self._messages: list[dict] = []
        self.names = dict(names or {})
        for message in messages or []:
            if isinstance(message, dict):
                self._add(message.get("role", "assistant"), message.get("content", ""))
            else:
                self._add(*message)

    def _add(self, role: object, content: object) -> Conversation:
        # 足した時点で確かめる。表示のときまで持ち越すと、どの行が悪いのか分からなくなる
        role = str(role)
        if role not in Chat.ROLES:
            raise ValueError(
                f"role は {list(Chat.ROLES)} のいずれかにしてください（指定値: {role!r}）"
            )
        self._messages.append({"role": role, "content": content})
        return self

    def reserve_reply(self) -> int:
        """あとから中身を入れる「相手の発言」の席を取り、その位置を返す。

        往復が重なったときに、答えが別の質問の下に付くのを防ぐための口。
        質問を足した直後にここで席を取っておけば、答えが遅れて届いても
        自分の質問のすぐ下に入る。足すだけなので、先に取った席の位置は動かない。
        """
        self._messages.append({"role": "assistant", "content": ""})
        return len(self._messages) - 1

    def fill_reply(self, at: int, content: object) -> Conversation:
        """:meth:`reserve_reply` で取った席に中身を入れる。"""
        self._messages[at]["content"] = content
        return self

    def say(self, content: object) -> Conversation:
        """利用者の発言を足す（右に出る）。"""
        return self._add("user", content)

    def reply(self, content: object) -> Conversation:
        """AI やボットの発言を足す（左に出る）。"""
        return self._add("assistant", content)

    def note(self, content: object) -> Conversation:
        """発言ではない補足を足す（真ん中に出る）。"""
        return self._add("note", content)

    def clear(self) -> Conversation:
        """会話を空に戻す。"""
        self._messages.clear()
        return self

    @property
    def messages(self) -> list[dict]:
        """いままでの会話。``ui.chat()`` にそのまま渡せる。

        写しを返すので、これを直接 append しても会話は増えない
        （増やすときは :meth:`say` / :meth:`reply` / :meth:`note` を使う）。
        """
        return [dict(message) for message in self._messages]

    def __len__(self) -> int:
        return len(self._messages)

    def _chat(self) -> Chat:
        return Chat(self._messages, names=self.names)

    # 中身が空のあいだも表示できるようにする（Chat は空を受け付けない）。
    # 最初のセルで作って、次のセルから足していく書き方を通すため。
    def _iter_css_keys(self) -> list[str]:
        if not self._messages:
            return list(self.css_keys)
        return self._chat()._iter_css_keys()

    def _iter_extra_css(self) -> list[str]:
        if not self._messages:
            return super()._iter_extra_css()
        return self._chat()._iter_extra_css()

    def fragment(self) -> str:
        if not self._messages:
            return '<div class="hui-chat"></div>'
        return self._chat().fragment()


def conversation(messages=None, names=None) -> Conversation:
    """会話をためておく入れ物。セルに置くと吹き出しで表示される。

    >>> talk = ui.conversation(names={"assistant": "ボット"})
    >>> talk.say("こんにちは")
    >>> talk.reply("やあ！")
    >>> talk

    ``ui.chat()`` との違いは、**あとから足せる**こと。往復するたびに辞書を
    組み立てる代わりに、``say()``（利用者）と ``reply()``（AI・ボット）を呼ぶ。
    ``note()`` は発言ではない補足で、真ん中に出る。

    ``content`` には文字列のほか、他の部品もそのまま入れられる。
    ``ai.talk()`` はこれを内側で使っている。
    """
    return Conversation(messages, names=names)


def chat(messages, names=None) -> Chat:
    """会話を吹き出しで表示する。

    ``messages`` は ``{"role": ..., "content": ...}`` の並び、または
    ``(role, content)`` の並び。role は user / assistant / note のいずれか。
    content には文字列のほか、他の部品もそのまま入れられる。

    >>> ui.chat([
    ...     {"role": "user", "content": "スマホは持っていっていい？"},
    ...     {"role": "assistant", "content": "はい、持ってきていいです。"},
    ... ])

    表示名は ``names={"user": "生徒", "assistant": "先生"}`` で変えられる。
    """
    return Chat(messages, names=names)
