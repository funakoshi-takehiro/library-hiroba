"""notebooks/ の各ノートブックが実際に動き、安全な出力になることを検証する。

配布するノートブックが壊れたまま気付かれないのを防ぐため、コードセルを
実際に実行し、表示される HTML をサニタイズ生存チェッカーに掛ける。
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from sanitize_check import check_html

import library_hiroba
from library_hiroba import ui

ROOT = Path(__file__).resolve().parents[1]
# examples/ も配るものなので同じ検査に掛ける。ここを notebooks/ だけにしていたため、
# school_rules_bot.ipynb は構文検査もサニタイザ検査も受けていなかった
NOTEBOOKS = sorted(
    list((ROOT / "notebooks").glob("*.ipynb")) + list((ROOT / "examples").glob("*.ipynb"))
)

# ai を使うノートブックは、動かすとモデル（数百 MB〜）の取得が始まるため実行しない。
# 実際に load → ask を通して確かめる手順は tools/check_ai_colab.py にある。
NOT_RUN = {"demo_ai.ipynb", "chat.ipynb", "book_search.ipynb", "school_rules_bot.ipynb"}


def code_cells(path: Path) -> list[tuple[str, str]]:
    """(セルID, ソース) の一覧。マジックコマンド（%pip 等）の行は取り除く。"""
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells = []
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        source = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith(("%", "!"))
        )
        if source.strip():
            cells.append((cell.get("id", str(i)), source))
    return cells


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_cells_compile(notebook):
    """実行しないノートブックも、少なくとも構文は壊れていないこと。

    セルの中の ``await``（``ai`` を呼ぶセル）はノートブックでは書けるので、
    同じ条件（トップレベルの await を許す）でコンパイルする。
    """
    assert NOTEBOOKS, "notebooks/ に .ipynb が見つかりません"
    for cell_id, source in code_cells(notebook):
        compile(source, cell_id, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_cells_run_and_render_safely(notebook):
    assert NOTEBOOKS, "notebooks/ に .ipynb が見つかりません"
    if notebook.name in NOT_RUN:
        pytest.skip("モデルの取得が要るため実行しない（tools/check_ai_colab.py で確認する）")
    env: dict = {}
    for cell_id, source in code_cells(notebook):
        tree = ast.parse(source)
        # ノートブックと同じ挙動: 最後が式ならその値が表示される
        last_expr = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last_expr = ast.Expression(tree.body.pop().value)
        exec(compile(tree, cell_id, "exec"), env)
        if last_expr is None:
            continue
        value = eval(compile(last_expr, cell_id, "eval"), env)
        # 部品を表示するセルだけ検証する（ui.__version__ のような確認セルは対象外。
        # ui.show() は Colab では None を返す）
        if isinstance(value, ui.Widget):
            violations = check_html(value._repr_html_())
            assert violations == [], f"{notebook.name}:{cell_id} → {violations}"


def raw_code(path: Path) -> str:
    """マジックコマンドも含めた、コードセルの中身すべて。"""
    nb = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell["source"]) for cell in nb["cells"] if cell["cell_type"] == "code"
    )


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_installs_the_newest_version(notebook):
    """``%pip install`` に ``-U`` が付いていること。

    Colab には古い library-hiroba が残っていることがあり、``-U`` が無いと
    「入っているから」で素通りする。直したはずの不具合がそのまま出続け、
    しかも版を確かめない限り気付けない（実際に2往復を費やした）。
    """
    for line in raw_code(notebook).splitlines():
        stripped = line.strip()
        if stripped.startswith(("%pip install", "!pip install")):
            assert " -U " in f" {stripped} ", f"{notebook.name}: -U がありません → {stripped}"


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_version_guard_is_not_ahead_of_the_release(notebook):
    """``NEEDS`` が、いま出ている版より先を指していないこと。

    逆向き（NEEDS が古いまま）も困る。修正を入れた版を NEEDS に上げ忘れると、
    見張りを素通りした古い版で、直したはずの不具合がそのまま出る。
    そちらは機械では判断できないので、ここでは上限だけを見る。
    """
    match = re.search(r'NEEDS\s*=\s*"([0-9]+(?:\.[0-9]+)*)"', raw_code(notebook))
    if match is None:
        return
    def numbers(text):
        return tuple(int(part) for part in text.split("."))
    assert numbers(match.group(1)) <= numbers(library_hiroba.__version__), (
        f"{notebook.name}: NEEDS={match.group(1)} は未公開の版です"
        f"（いまの __version__ は {library_hiroba.__version__}）"
    )
