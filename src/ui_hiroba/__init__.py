"""ui_hiroba — Colab と PyHiroba の両方で動く、サーバー不要の教育向け UI 表示ライブラリ。

使い方（セル最後の式に置くと表示される）::

    import ui_hiroba as ui

    ui.card("今日の目標", "for文を使って、九九の表を作ってみよう！")

仕組み: 各部品は ``_repr_html_()`` で自己完結な HTML/CSS を返す。
JavaScript もサーバーも使わないため、ブラウザ内完結の PyHiroba でも
Google Colab のサンドボックス iframe でも同じように表示される。
"""

from ._components import (
    alert,
    badge,
    card,
    columns,
    html,
    progress,
    quiz,
    reveal,
    stack,
    stat,
    table,
)
from ._core import Widget, show

__version__ = "0.1.0"

__all__ = [
    "Widget",
    "alert",
    "badge",
    "card",
    "columns",
    "html",
    "progress",
    "quiz",
    "reveal",
    "show",
    "stack",
    "stat",
    "table",
    "__version__",
]
