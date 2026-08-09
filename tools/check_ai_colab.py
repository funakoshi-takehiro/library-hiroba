"""Colab 経路（transformers + torch）を実際に動かして確かめる。

    pip install "library-hiroba[ai]"
    python tools/check_ai_colab.py                 # 一番軽い llmjp150m で確かめる
    python tools/check_ai_colab.py --model qwen05  # 既定のモデルで確かめる
    python tools/check_ai_colab.py --model auto    # 環境を調べて選ばせる

``--model auto`` は、この機械で調べがついた内容と、そこから選ばれたモデルを
先に表示する。GPU の有る Colab と無い Colab の両方で走らせて、選ばれたものが
実際の速さと釣り合っているかを見るのが、環境判定のいちばん確かな確かめ方。

初回はモデルの取得（数百 MB〜）が始まるため、単体テストからは実行しない。
Colab で確かめるときは、ノートブックのセルに次を貼ってもよい。

    !pip install -q "library-hiroba[ai]"
    from library_hiroba import ai
    print(await ai.load("llmjp150m"))
    print(await ai.ask("日本の四季について、2行で書いて", max_tokens=48))
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from library_hiroba import ai  # noqa: E402
from library_hiroba._ai import MODELS, in_browser  # noqa: E402


async def check(model: str, prompt: str, max_tokens: int) -> int:
    if in_browser():
        print("ここはブラウザ（PyHiroba）です。この確認は Colab 経路が対象です。")
        return 1

    found = await ai.environment()
    print("調べた環境:")
    for key in ("known", "label", "ram_gb", "vram_gb", "cores", "storage_mb"):
        print(f"  {key:<11} {found[key]}")

    if model == "auto":
        chosen = await ai.recommend()
        print(f"\nおすすめ: {chosen.name}\n  {chosen.reason}")
        model = chosen.name

    print(f"\nモデル: {model}")
    for entry in await ai.models():
        mark = "→" if entry["name"] == model else " "
        print(f"  {mark} {entry['name']:<10} {entry['approxMB']:>5}MB  {entry['label']}")

    started = time.time()
    print(await ai.load(model))
    print(f"  読み込み: {time.time() - started:.1f} 秒")

    started = time.time()
    answer = await ai.ask(prompt, max_tokens=max_tokens)
    print(f"  生成: {time.time() - started:.1f} 秒")

    print(f"\n質問: {prompt}")
    print(f"答え: {answer}")

    if not isinstance(answer, str) or not answer.strip():
        print("\n失敗: 空の答えが返りました")
        return 1
    print("\nOK: load → ask が通りました")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="llmjp150m", choices=[*MODELS, "auto"])
    parser.add_argument("--prompt", default="日本の四季について、2行で書いて")
    parser.add_argument("--max-tokens", type=int, default=48)
    args = parser.parse_args()
    return asyncio.run(check(args.model, args.prompt, args.max_tokens))


if __name__ == "__main__":
    raise SystemExit(main())
