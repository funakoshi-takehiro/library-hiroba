"""ウィジェット基盤: 表示プロトコル・エスケープ・CSS 集約・合成。"""

from __future__ import annotations

import html as _html
import secrets
from collections.abc import Sequence
from typing import Union

from ._css import BASE_CSS, COMPONENT_CSS


def esc(value: object) -> str:
    """本文テキスト用エスケープ。改行は ``<br>`` にする。"""
    return _html.escape(str(value), quote=True).replace("\n", "<br>")


def esc_attr(value: object) -> str:
    """属性値用エスケープ（改行変換なし）。"""
    return _html.escape(str(value), quote=True)


def unique_name(prefix: str = "hui") -> str:
    """document 全体で衝突しない一意な名前を返す。

    PyHiroba では全セルの出力が 1 つの document を共有するため、
    radio の ``name`` などはウィジェットごとに一意でなければならない。
    """
    return f"{prefix}-{secrets.token_hex(4)}"


class Widget:
    """全 UI 部品の基底クラス。

    セル最後の式に置くと、Colab / Jupyter / PyHiroba がいずれも解釈する
    ``_repr_html_()`` プロトコルによって HTML として表示される。
    出力は自己完結（必要な CSS を同梱）で、JavaScript を一切含まない。
    """

    css_keys: tuple[str, ...] = ()

    def fragment(self) -> str:
        """``<style>`` を含まないマークアップ断片を返す。"""
        raise NotImplementedError

    def _iter_css_keys(self) -> list[str]:
        return list(self.css_keys)

    def _style_block(self) -> str:
        needed = set(self._iter_css_keys())
        # COMPONENT_CSS の定義順を保って必要な分だけ連結（重複なし）
        parts = [BASE_CSS] + [css for key, css in COMPONENT_CSS.items() if key in needed]
        return "<style>\n" + "\n".join(parts) + "\n</style>"

    def _repr_html_(self) -> str:
        return f'{self._style_block()}\n<div class="hui">\n{self.fragment()}\n</div>'

    def __repr__(self) -> str:
        return f"<ui_hiroba.{type(self).__name__}>"


Item = Union[Widget, object]


class Text(Widget):
    """プレーン文字列を安全に表示する部品。コンテナに str を渡すと使われる。"""

    css_keys = ("text",)

    def __init__(self, text: object):
        self.text = text

    def fragment(self) -> str:
        return f'<div class="hui-text">{esc(self.text)}</div>'


def as_widget(item: Item) -> Widget:
    return item if isinstance(item, Widget) else Text(item)


class Container(Widget):
    """子ウィジェットを持つ部品。CSS は子の分まで再帰的に集約する。"""

    def __init__(self, items: Sequence[Item]):
        if not items:
            raise ValueError("表示する部品を1つ以上渡してください")
        self.children = [as_widget(x) for x in items]

    def _iter_css_keys(self) -> list[str]:
        keys = list(self.css_keys)
        for child in self.children:
            keys.extend(child._iter_css_keys())
        return keys


class Stack(Container):
    """複数の部品を縦に積むコンテナ。"""

    css_keys = ("stack",)

    def __init__(self, items: Sequence[Item], gap: str = "12px"):
        super().__init__(items)
        self.gap = gap

    def fragment(self) -> str:
        inner = "\n".join(c.fragment() for c in self.children)
        return f'<div class="hui-stack" style="gap: {esc_attr(self.gap)};">\n{inner}\n</div>'


def show(*items: Item):
    """部品を表示するヘルパー。

    - Colab / Jupyter: その場で表示して ``None`` を返す（セル途中でも表示できる）。
    - PyHiroba（IPython なし）: 部品（複数なら縦積み）を返すので、
      セル最後の式として置けば表示される。
    """
    if not items:
        raise ValueError("表示する部品を1つ以上渡してください")
    widget = as_widget(items[0]) if len(items) == 1 else Stack(items)
    try:
        from IPython.display import display
    except ImportError:
        return widget
    display(widget)
    return None
