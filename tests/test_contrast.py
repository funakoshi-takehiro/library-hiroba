"""配色のコントラスト比を数値で固定する。

README に「本文と状態色は 4.5:1 以上」と書いてあるが、これまで人の目でしか
確かめていなかった。配色を触ったときに気付けるよう、実際に計算して確かめる。

基準（WCAG 2.1）:

- 1.4.3 本文の文字     4.5:1 以上
- 1.4.3 大きい文字     3:1 以上（18.66px 太字 または 24px から）
- 1.4.11 UI 部品・図形 3:1 以上
"""

from __future__ import annotations

import re

import pytest

from library_hiroba._css import BASE_CSS


def theme_tokens(selector: str) -> dict[str, str]:
    block = re.search(re.escape(selector) + r"\s*\{(.*?)\}", BASE_CSS, re.S)
    assert block, f"{selector} の定義が見つかりません"
    return dict(re.findall(r"(--hui-[a-z0-9-]+)\s*:\s*([^;]+);", block.group(1)))


LIGHT = theme_tokens(".hui")
DARK = {**LIGHT, **theme_tokens('[data-theme="dark"] .hui')}


def relative_luminance(color: str) -> float:
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    channels = []
    for i in (0, 2, 4):
        c = int(value[i : i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: str, background: str) -> float:
    a, b = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_helper_matches_known_values():
    """計算式そのものが正しいことを、答えの分かっている組で確かめる。"""
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#ffffff", "#ffffff") == pytest.approx(1.0)
    assert contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


# 本文として読む文字。4.5:1 を下回ってはいけない
BODY_TEXT = [
    ("本文", "--hui-ink", "--hui-paper"),
    ("本文（面2の上）", "--hui-ink", "--hui-bg-2"),
    ("補助の文字", "--hui-ink-2", "--hui-paper"),
    ("薄い文字", "--hui-ink-3", "--hui-paper"),
    ("アクセントの文字", "--hui-accent-ink", "--hui-accent-soft"),
    ("できましたの文字", "--hui-ok-ink", "--hui-ok-soft"),
    ("注意の文字", "--hui-warn-ink", "--hui-warn-soft"),
    ("警告の文字", "--hui-bad-ink", "--hui-bad-soft"),
]


@pytest.mark.parametrize("theme,tokens", [("light", LIGHT), ("dark", DARK)])
@pytest.mark.parametrize("label,ink,paper", BODY_TEXT, ids=[p[0] for p in BODY_TEXT])
def test_body_text_meets_4_5(theme, tokens, label, ink, paper):
    ratio = contrast(tokens[ink], tokens[paper])
    assert ratio >= 4.5, f"{theme} の{label}が {ratio:.2f}:1（4.5:1 が必要）"


def test_text_on_accent_is_documented_as_it_is():
    """アクセント色を塗った上の文字。

    ライトは 3.87:1 で、UI 部品の基準（3:1）は満たすが本文の基準には届かない。
    使っているのは送信ボタンと alert の丸いマークの2か所で、README にもその
    まま書いてある。下地を --hui-accent-ink にすれば 5.46:1 になるが、
    PyHiroba 本体のブランド色の使い方から外れるため、そのままにしてある。
    数値が動いたら README も直す必要があるので、ここで固定しておく。
    """
    light = contrast(LIGHT["--hui-on-accent"], LIGHT["--hui-accent"])
    dark = contrast(DARK["--hui-on-accent"], DARK["--hui-accent"])
    assert light == pytest.approx(3.87, abs=0.01), "README の 3.87:1 という記述と合いません"
    assert light >= 3.0, "UI 部品の基準（3:1）は必ず満たすこと"
    assert dark >= 4.5, f"ダークは本文の基準を満たしていたはず（いま {dark:.2f}:1）"
