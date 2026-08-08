"""PyHiroba のサニタイザ（DOMPurify ベース）を通しても出力が変化しないことの近似検証。

PyHiroba は script・イベント属性(on*)・iframe・form などを出力から除去する。
このチェッカーは「除去対象がそもそも出力に含まれない」ことを検証することで、
サニタイズ前後で表示が変わらない（= 両環境で同一表示になる）ことを保証する。

あわせてプロジェクト独自の不変条件も検査する:

- ``id`` 属性を使わない（PyHiroba では全セルが 1 document を共有するため、
  id はセル間で衝突しうる）
- タグの開閉が対応している（壊れたマークアップはホスト DOM を巻き込む）
"""

from __future__ import annotations

from html.parser import HTMLParser

FORBIDDEN_TAGS = frozenset(
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

URL_ATTRS = frozenset({"href", "src", "action", "formaction", "xlink:href", "data"})

VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


class _Checker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.violations: list[str] = []
        self.open_tags: list[str] = []

    def _check_attrs(self, tag: str, attrs) -> None:
        for name, value in attrs:
            lowered = name.lower()
            if lowered.startswith("on"):
                self.violations.append(f"<{tag}> にイベント属性 {name} がある")
            if lowered == "id":
                self.violations.append(f"<{tag}> に id 属性がある（セル間で衝突しうる）")
            if lowered in URL_ATTRS and value is not None:
                normalized = "".join(value.split()).lower()
                if normalized.startswith("javascript:"):
                    self.violations.append(f"<{tag} {name}> が javascript: URL")

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in FORBIDDEN_TAGS:
            self.violations.append(f"禁止タグ <{tag}> がある")
        self._check_attrs(tag, attrs)
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag in FORBIDDEN_TAGS:
            self.violations.append(f"禁止タグ <{tag}/> がある")
        self._check_attrs(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if not self.open_tags or self.open_tags[-1] != tag:
            self.violations.append(
                f"タグの開閉が対応していない: </{tag}> (開いているタグ: {self.open_tags!r})"
            )
        else:
            self.open_tags.pop()


def check_html(html_text: str) -> list[str]:
    """違反のリストを返す。空リストなら合格。"""
    checker = _Checker()
    checker.feed(html_text)
    checker.close()
    if checker.open_tags:
        checker.violations.append(f"閉じられていないタグがある: {checker.open_tags!r}")
    return checker.violations
