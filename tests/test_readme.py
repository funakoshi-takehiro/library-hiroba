"""README のモデル表が、実際の設定とずれていないか確かめる。

利用者は README の数字を見て、校内の回線で配れるかを決める。表を手で書き写す
かぎり必ずずれるので、`MODELS` と突き合わせる。実際に一度ずれた（`llmjp150m`
の Colab 側を 600MB から 1.5GB と書き間違えた）ので、これはその再発防止。
"""

from __future__ import annotations

import pathlib
import re

import pytest

from library_hiroba._ai import MODELS

README = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text("utf-8")

# | `qwen05`（既定） | Qwen2.5 0.5B。… | 約 900MB ／ 約 1.0GB |
ROW = re.compile(
    r"^\|\s*`([a-z0-9_]+)`[^|]*\|[^|]*\|\s*約\s*([\d.]+)(MB|GB)\s*／\s*約\s*([\d.]+)(MB|GB)\s*\|",
    re.M,
)


def _to_mb(amount: str, unit: str) -> float:
    return float(amount) * (1000 if unit == "GB" else 1)


DOCUMENTED = {
    name: {"browser": _to_mb(a1, u1), "colab": _to_mb(a2, u2)}
    for name, a1, u1, a2, u2 in ROW.findall(README)
}


def test_the_table_was_found_at_all():
    """読み取れていないのに「ずれ無し」と言わないための足場。"""
    assert DOCUMENTED, "README のモデル表を読み取れませんでした（書式が変わった？）"


def test_the_table_lists_every_model():
    assert set(DOCUMENTED) == set(MODELS), (
        f"README にしか無い: {sorted(set(DOCUMENTED) - set(MODELS))} / "
        f"README に足りない: {sorted(set(MODELS) - set(DOCUMENTED))}"
    )


@pytest.mark.parametrize("name", sorted(MODELS))
@pytest.mark.parametrize("where", ["browser", "colab"])
def test_the_sizes_match(name, where):
    written = DOCUMENTED.get(name, {}).get(where)
    actual = MODELS[name]["approx_mb"][where]
    assert written == actual, (
        f"{name} の{'ブラウザ' if where == 'browser' else 'Colab'}側: "
        f"README は {written}MB、_ai.py は {actual}MB"
    )


def test_the_table_is_ordered_lightest_first():
    """README が「軽いものから順に」と書いているとおりに並んでいること。"""
    # DOCUMENTED は表の並び順のまま作っている（辞書は入れた順を保つ）
    order = [DOCUMENTED[name]["browser"] for name in DOCUMENTED]
    assert order == sorted(order), f"ブラウザ側の通信量が昇順になっていません: {order}"
