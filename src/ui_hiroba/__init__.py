"""ui_hiroba — Google Colab と PyHiroba で動く、教育向けの UI 表示ライブラリ。

使い方（セル最後の式に置くと表示される）::

    import ui_hiroba as ui

    ui.card("今日の目標", "for文を使って、九九の表を作ってみよう！")

用意された部品のほかに、``ui.html()`` で HTML と CSS を自由に書ける::

    ui.html('<div class="memo">ヒント</div>',
            css=".memo { border: 2px solid var(--hui-accent); }")

しくみ: 各部品は ``_repr_html_()`` で自己完結の HTML と CSS を返す。
表示も操作も HTML と CSS だけで完結するため、ブラウザ内で動く PyHiroba
（https://pyhiroba.weblab.t.u-tokyo.ac.jp/）でも、Google Colab の
サンドボックス iframe でも同じように表示される。
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
    "__version__",
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
]
