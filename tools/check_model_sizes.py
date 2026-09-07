"""MODELS に書いた通信量が、配布元の実際の大きさと合っているかを確かめる。

    python tools/check_model_sizes.py

**設計図だけを数えないこと。** 大きなモデルの ONNX は、設計図（``model_q4.onnx``、
数百 KB）と重み（``model_q4.onnx_data``、続きがあれば ``_data_1`` ``_data_2`` …）に
分かれる。設計図だけを見ると 448MB を 0.6MB と数えてしまう。本体側が実際にこれを
踏んで「使えるモデルを調べる」機能が誤った数を出していた（2026-09）。こちらの表も
同じ日に測り直し、3件のずれと、空き容量の下限が実サイズを下回る不具合が見つかった。

通信が要るので、テストからは呼ばない（CI を配布元の都合で落とさないため）。
モデルを足したとき・上流が更新されたときに手で回す。
"""

from __future__ import annotations

import collections
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library_hiroba._ai import MODELS

# browser_key の末尾（dtype）から、配布元のファイル名を引く
FILE_FOR = {
    "q8": ("model_quantized", "model_int8", "model_uint8"),
    "q4": ("model_q4",),
    "q4f16": ("model_q4f16",),
    "fp16": ("model_fp16",),
}
ALLOWED_DRIFT = 0.10  # 目安なので1割までは許す（切り上げてあるぶんを含む）


def variant_sizes(repo: str) -> dict[str, int]:
    """``onnx/`` の中を変種ごとに合計する（外部データのファイルも足す）。"""
    url = f"https://huggingface.co/api/models/{repo}?blobs=true"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    totals: dict[str, int] = collections.defaultdict(int)
    for sibling in payload.get("siblings", []):
        name = sibling["rfilename"]
        if not name.startswith("onnx/"):
            continue
        match = re.match(r"^(.*?)\.onnx(_data(_\d+)?)?$", name.split("/")[-1])
        if match:
            totals[match.group(1)] += sibling.get("size") or 0
    return dict(totals)


def main() -> int:
    problems = 0
    print(f"{'名前':11} {'変種':8} {'表の値':>8} {'実測':>8}  判定")
    for name, spec in MODELS.items():
        dtype = spec["browser_key"].rsplit("-", 1)[-1]
        written = spec["approx_mb"]["browser"]
        try:
            found = variant_sizes(spec["browser_repo"])
        except (urllib.error.URLError, urllib.error.HTTPError) as error:
            print(f"{name:11} {dtype:8} {written:>6}MB {'—':>8}  取得できず: {error}")
            problems += 1
            continue
        size = next((found[f] for f in FILE_FOR.get(dtype, ()) if f in found), None)
        if size is None:
            print(
                f"{name:11} {dtype:8} {written:>6}MB {'—':>8}  "
                f"★ その変種がありません（あるのは {sorted(found)}）"
            )
            problems += 1
            continue
        actual = round(size / 1e6)
        note = "OK"
        if abs(actual - written) / max(actual, 1) > ALLOWED_DRIFT:
            note = f"★ 表とずれています（{written} → {actual} に直す）"
            problems += 1
        # 空き容量の下限は tests/test_ai.py が表の値と突き合わせている。
        # ここでは実測とも比べる（表を直し忘れても気付けるように）
        floor = spec["needs"]["browser"]["storage_mb"]
        if floor < actual:
            note += f"／★ 空き容量の下限 {floor}MB が実サイズ {actual}MB を下回ります"
            problems += 1
        print(f"{name:11} {dtype:8} {written:>6}MB {actual:>6}MB  {note}")

    print()
    print("問題なし" if not problems else f"要確認 {problems} 件")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
