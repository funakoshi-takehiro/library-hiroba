"""notebooks/ の各ノートブックが実際に動き、安全な出力になることを検証する。

配布するノートブックが壊れたまま気付かれないのを防ぐため、コードセルを
実際に実行し、表示される HTML をサニタイズ生存チェッカーに掛ける。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from sanitize_check import check_html

import ui_hiroba as ui

NOTEBOOKS = sorted((Path(__file__).resolve().parents[1] / "notebooks").glob("*.ipynb"))


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
def test_notebook_cells_run_and_render_safely(notebook):
    assert NOTEBOOKS, "notebooks/ に .ipynb が見つかりません"
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
