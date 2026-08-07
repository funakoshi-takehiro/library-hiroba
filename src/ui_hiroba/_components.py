"""10個の UI 部品と、それを生成する小文字のファクトリ関数。

すべての部品はテキスト引数を HTML エスケープする。エスケープしない唯一の
経路は :func:`html`（明示的な逃げ道）だけ。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Union

from ._core import (
    Container,
    Item,
    Stack,
    Widget,
    esc,
    esc_attr,
    unique_name,
)

Number = Union[int, float]


class Card(Widget):
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

    def fragment(self) -> str:
        parts = []
        if self.title:
            icon = f'<span class="hui-card-icon">{esc(self.icon)}</span>' if self.icon else ""
            parts.append(f'<div class="hui-card-title">{icon}<span>{esc(self.title)}</span></div>')
        if self.body != "" and self.body is not None:
            parts.append(f'<div class="hui-card-body">{esc(self.body)}</div>')
        if self.footer is not None:
            parts.append(f'<div class="hui-card-footer">{esc(self.footer)}</div>')
        return f'<div class="hui-card">{"".join(parts)}</div>'


class Alert(Widget):
    css_keys = ("alert",)

    ICONS = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "danger": "🚨"}

    def __init__(self, message: object, kind: str = "info", title: object = None):
        if kind not in self.ICONS:
            raise ValueError(
                f"kind は {sorted(self.ICONS)} のいずれかにしてください（指定値: {kind!r}）"
            )
        self.message = message
        self.kind = kind
        self.title = title

    def fragment(self) -> str:
        kind_class = "" if self.kind == "info" else f" hui-alert-{self.kind}"
        title = f'<div class="hui-alert-title">{esc(self.title)}</div>' if self.title else ""
        return (
            f'<div class="hui-alert{kind_class}">'
            f'<span class="hui-alert-icon">{self.ICONS[self.kind]}</span>'
            f"<div>{title}<div>{esc(self.message)}</div></div>"
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
        incorrect_text: str = "✗ ざんねん…",
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


class Reveal(Widget):
    css_keys = ("reveal",)

    def __init__(self, content: object, summary: object = "答えを見る"):
        self.content = content
        self.summary = summary

    def fragment(self) -> str:
        return (
            f'<details class="hui-reveal"><summary>{esc(self.summary)}</summary>'
            f'<div class="hui-reveal-body">{esc(self.content)}</div></details>'
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
        max_value = float(max)
        if max_value <= 0:
            raise ValueError(f"max は正の数にしてください（指定値: {max!r}）")
        self.value = float(value)
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


class Stat(Widget):
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

    def fragment(self) -> str:
        icon = f"{esc(self.icon)} " if self.icon else ""
        unit = f'<span class="hui-stat-unit">{esc(self.unit)}</span>' if self.unit else ""
        return (
            f'<div class="hui-stat">'
            f'<span class="hui-stat-label">{icon}{esc(self.label)}</span>'
            f'<span class="hui-stat-value">{esc(self.value)}{unit}</span>'
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
            widths = [float(w) for w in widths]
            if len(widths) != len(self.children):
                raise ValueError(
                    f"widths の数（{len(widths)}）を部品の数（{len(self.children)}）に合わせてください"
                )
            if any(w <= 0 for w in widths):
                raise ValueError(f"widths は正の数にしてください（指定値: {widths!r}）")
        self.widths = widths
        self.gap = gap

    def fragment(self) -> str:
        cols = []
        for i, child in enumerate(self.children):
            style = f' style="flex: {self.widths[i]:.4g} 1 0;"' if self.widths else ""
            cols.append(f'<div class="hui-col"{style}>{child.fragment()}</div>')
        return (
            f'<div class="hui-cols" style="gap: {esc_attr(self.gap)};">{"".join(cols)}</div>'
        )


class Badge(Widget):
    css_keys = ("badge",)

    COLORS = ("blue", "green", "red", "amber", "gray")

    def __init__(self, text: object, color: str = "blue"):
        if color not in self.COLORS:
            raise ValueError(
                f"color は {list(self.COLORS)} のいずれかにしてください（指定値: {color!r}）"
            )
        self.text = text
        self.color = color

    def fragment(self) -> str:
        color_class = "" if self.color == "gray" else f" hui-badge-{self.color}"
        return f'<span class="hui-badge{color_class}">{esc(self.text)}</span>'


class Table(Widget):
    css_keys = ("table",)

    def __init__(
        self,
        data: Sequence[object],
        headers: Sequence[object] | None = None,
        caption: object = None,
    ):
        rows = list(data)
        if not rows:
            raise ValueError("data が空です")
        if all(isinstance(r, dict) for r in rows):
            if headers is None:
                headers = []
                for r in rows:
                    for key in r:
                        if key not in headers:
                            headers.append(key)
            self.rows = [[r.get(h, "") for h in headers] for r in rows]
        else:
            self.rows = [list(r) for r in rows]
        self.headers = list(headers) if headers is not None else None
        self.caption = caption

    def fragment(self) -> str:
        caption = f"<caption>{esc(self.caption)}</caption>" if self.caption is not None else ""
        thead = ""
        if self.headers is not None:
            cells = "".join(f"<th>{esc(h)}</th>" for h in self.headers)
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


class RawHtml(Widget):
    css_keys = ()

    def __init__(self, raw: object, css: str | None = None, scoped: bool = True):
        self.raw = str(raw)
        self.css = None if css is None else _STYLE_CLOSE_RE.sub(lambda _: "<\\/style", str(css))
        # scoped の場合はインスタンスごとに一意なクラスで CSS の効く範囲を限定する
        # （PyHiroba では全セルが 1 document を共有するため、ページや他セルを汚さない）
        self.scope_class = unique_name("hui-raw") if (self.css is not None and scoped) else None

    def extra_css(self) -> str:
        if self.css is None:
            return ""
        if self.scope_class is not None:
            # CSS ネスト（モダンブラウザ標準）でユーザー CSS 全体をスコープする
            return f".{self.scope_class} {{\n{self.css}\n}}"
        return self.css

    def fragment(self) -> str:
        cls = "hui-raw" if self.scope_class is None else f"hui-raw {self.scope_class}"
        return f'<div class="{cls}">{self.raw}</div>'


# ---------------------------------------------------------------------------
# 公開 API（ファクトリ関数）
# ---------------------------------------------------------------------------


def card(title, body="", icon=None, footer=None) -> Card:
    """説明カード。

    >>> ui.card("今日の目標", "for文を使って、九九の表を作ってみよう！", icon="🎯")
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
    incorrect_text="✗ ざんねん…",
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

    >>> ui.stat("正答率", 85, unit="%", icon="📈")
    """
    return Stat(label, value, unit=unit, icon=icon)


def columns(*items, widths=None, gap="12px") -> Columns:
    """部品を横並びに配置する。狭い画面では自動で折り返す。

    >>> ui.columns(ui.stat("得点", 90), ui.stat("順位", 3))
    """
    return Columns(items, widths=widths, gap=gap)


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

    渡した内容がそのまま出力に含まれるため、信頼できる内容にだけ使うこと。
    PyHiroba 上では表示前に本体側のサニタイザ（DOMPurify）が適用されるため、
    script などはそこで除去される。
    """
    return RawHtml(raw, css=css, scoped=scoped)


def stack(*items, gap="12px") -> Stack:
    """複数の部品を縦に積んで 1 つの表示にまとめる。

    >>> ui.stack(ui.card("目標", "..."), ui.progress(3, max=10))
    """
    return Stack(items, gap=gap)
