from __future__ import annotations

import re
import sys
from pathlib import Path

# pip install なしでも src レイアウトのパッケージを import できるようにする
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ui_hiroba as ui


def has_rule(html: str, selector: str) -> bool:
    """CSS に selector の規則が含まれるか。

    CSS は読み込み時に縮められるため、``{`` の前の空白の有無に依存しない形で調べる。
    """
    return re.search(re.escape(selector) + r"\s*\{", html) is not None


def sample_widgets(text: str = "サンプル") -> dict[str, ui.Widget]:
    """全部品を text 入りで生成する。不変条件テストが全部品を舐めるための入口。

    新しい部品を追加したら、ここにも必ず追加すること。
    """
    t = text
    return {
        "card": ui.card(t, t + "\n2行目", icon="[1]", footer=t),
        "alert_info": ui.alert(t),
        "alert_success": ui.alert(t, kind="success", title=t),
        "alert_warning": ui.alert(t, kind="warning"),
        "alert_danger": ui.alert(t, kind="danger", title=t),
        "quiz": ui.quiz(t + "?", [t + "A", t + "B", t + "C"], t + "B", explanation=t),
        "quiz_no_explanation": ui.quiz(t + "?", [t + "1", t + "2"], t + "1"),
        "reveal": ui.reveal(t, summary=t),
        "progress": ui.progress(7, max=10, label=t),
        "stat": ui.stat(t, 85, unit="%", icon="*"),
        "columns": ui.columns(ui.stat(t, 1), ui.stat(t + "2", 2), widths=[2, 1]),
        "badge": ui.badge(t, color="amber"),
        "table_dicts": ui.table([{t + "列1": t, t + "列2": 1}, {t + "列1": t, t + "列2": 2}]),
        "table_lists": ui.table([[1, 2], [3, 4]], headers=[t, t + "2"], caption=t),
        "stack": ui.stack(ui.card(t), t + " プレーン文字列"),
    }
