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


def weight_size(repo: str) -> int:
    """Colab 側の通信量。重みのファイル（分割されていれば全部）を足す。

    こちらは長いあいだ検査していなかった。そのあいだに qwen3_17 が 664MB 過小
    （表 3400MB・実測 4064MB）、llmjp150m が約2倍過大（600MB・実測 305MB）に
    なっていた。ブラウザ側だけ見ていたのが理由。
    """
    url = f"https://huggingface.co/api/models/{repo}?blobs=true"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    return sum(
        sibling.get("size") or 0
        for sibling in payload.get("siblings", [])
        if sibling["rfilename"].endswith((".safetensors", ".bin"))
    )


def storage_floor(actual_mb: int) -> int:
    """空き容量の下限として最低限ほしい値（実サイズの 1.5 倍）。"""
    return round(actual_mb * 1.5)


def memory_order_problems() -> list[str]:
    """要求メモリの並びが実サイズの並びと合っていないものを挙げる。

    小さいモデルのほうが多くのメモリを要求していると、2〜3GB の端末で
    「より小さくて新しいほうが外れる」が起きる。数字は手書きなので直すには
    実機の測定が要る。ここでは**見えるようにする**（黙って残らないように）。
    """
    by_size = sorted(MODELS.items(), key=lambda kv: kv[1]["approx_mb"]["browser"])
    found = []
    for i, (name, spec) in enumerate(by_size):
        mine = spec["needs"]["browser"]["memory_gb"]
        for bigger, other in by_size[i + 1 :]:
            if other["needs"]["browser"]["memory_gb"] < mine:
                found.append(
                    f"{name}（{spec['approx_mb']['browser']}MB → {mine}GB）より "
                    f"{bigger}（{other['approx_mb']['browser']}MB → "
                    f"{other['needs']['browser']['memory_gb']}GB）のほうが要求が小さい"
                )
    return found


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
        want = storage_floor(actual)
        if floor < want:
            note += f"／★ 空き容量の下限 {floor}MB が実サイズの1.5倍（{want}MB）に足りません"
            problems += 1
        print(f"{name:11} {dtype:8} {written:>6}MB {actual:>6}MB  {note}")

    print()
    print(f"{'名前':11} {'Colab の表':>10} {'実測':>8}  判定")
    for name, spec in MODELS.items():
        written = spec["approx_mb"]["colab"]
        try:
            size = weight_size(spec["colab_id"])
        except (urllib.error.URLError, urllib.error.HTTPError) as error:
            print(f"{name:11} {written:>8}MB {'—':>8}  取得できず: {error}")
            problems += 1
            continue
        actual = round(size / 1e6)
        note = "OK"
        if abs(actual - written) / max(actual, 1) > ALLOWED_DRIFT:
            note = f"★ 表とずれています（{written} → {actual} に直す）"
            problems += 1
        print(f"{name:11} {written:>8}MB {actual:>6}MB  {note}")

    print()
    inversions = memory_order_problems()
    if inversions:
        print("要求メモリの並びが実サイズと合っていません（実機で測って直すこと）:")
        for line in inversions:
            print(f"  ・{line}")
        print("  ※ 数字を測らずに書き換えないこと。動いていた端末が動かなくなる向きに転びうる")
    print()
    if problems:
        print(f"要確認 {problems} 件")
    elif inversions:
        # ここで「問題なし」と出すと、すぐ上に並べた崩れを打ち消してしまう
        print(f"通信量のずれは無し。ただし要求メモリの並びは未解決（上記 {len(inversions)} 件）")
    else:
        print("問題なし")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
