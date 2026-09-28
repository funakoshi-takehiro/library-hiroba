from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

# pip install なしでも src レイアウトのパッケージを import できるようにする
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library_hiroba import ui


def require_torch():
    """torch を要求する。手元では無ければ飛ばし、CI では落とす。

    Colab 経路（平均プーリング・埋め込みの鍵・二重読み込み）の見張りは torch が
    無いと動かない。``pytest.importorskip`` をそのまま書くと、CI の依存から torch が
    抜けた日に**静かに skip へ戻り**、緑のまま誰も気付かない。実際そうなっていた。

    そのため CI では ``HIROBA_REQUIRE_AI=1`` を立て、torch が無いこと自体を
    失敗として扱う。手元では今までどおり飛ばす。
    """
    if os.environ.get("HIROBA_REQUIRE_AI") == "1":
        import torch  # noqa: F401 — 無ければ ImportError をそのまま出す（skip しない）

        return sys.modules["torch"]
    return pytest.importorskip("torch")


def require_ipywidgets():
    """ipywidgets を要求する。手元では無ければ飛ばし、CI では落とす。

    Colab 経路（フォームの表示と押下）の見張りは ipywidgets が無いと動かない。
    この経路は**これまで手書きの代役でしか試しておらず**、そのあいだに
    「押しても何も起きない」が3回出た（うち1回は容器に入れたときの取りこぼし）。
    本物を相手にする検査を CI で必ず回すため、``dev`` に入れてある。
    """
    if os.environ.get("HIROBA_REQUIRE_AI") == "1":
        import ipywidgets  # noqa: F401

        return sys.modules["ipywidgets"]
    return pytest.importorskip("ipywidgets")


def without_ipython(monkeypatch) -> None:
    """IPython が無い環境（PyHiroba）にする。

    ``"IPython" in sys.modules`` を見て skip すると、ipywidgets（ipython を
    連れてくる）を入れた環境では**その検査がまるごと走らなくなる**。
    隠せば、どちらの環境でも同じ検査ができる。
    """
    for name in ("IPython", "IPython.display"):
        monkeypatch.setitem(sys.modules, name, None)


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
        "chat": ui.chat(
            [{"role": "user", "content": t}, {"role": "assistant", "content": t + "の答え"}],
            names={"user": t, "assistant": t + "先生"},
        ),
        "chat_widgets": ui.chat([("note", ui.badge(t)), ("assistant", ui.card(t, t))]),
        "form": ui.form(
            lambda a, b, c: a,
            ui.field("a", label=t, placeholder=t, default=t),
            ui.field("b", label=t, kind="multiline", default=t + "\n2行目"),
            ui.field("c", label=t, kind="choice", choices=[t + "甲", t + "乙"]),
            submit_label=t,
            title=t,
        ),
    }
