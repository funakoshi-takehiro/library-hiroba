"""小さな言語モデルを、PyHiroba でも Colab でも同じ書き方で動かす。

    from library_hiroba import ai

    await ai.load()
    print(await ai.ask("日本の四季について、2行で書いて"))

なぜ ``await`` が要るか
----------------------
PyHiroba は GitHub Pages で配信しているため COOP/COEP ヘッダを付けられず、
``SharedArrayBuffer`` を使った同期待ちができません。そのためブラウザ側では
「待つ」処理にせざるを得ません。Colab 側は待つ必要がありませんが、
**同じコードが両方で動く**ことを優先して、こちらも ``await`` の形に揃えています。
ノートブック（Colab / Jupyter / PyHiroba）は、セルの中でそのまま ``await`` が使えます。

2つの経路
---------
- PyHiroba（ブラウザ）… 本体が用意した ``js.pyhirobaAsk`` を通す。やり取りは JSON 文字列だけ
- Colab など … ``transformers`` と ``torch`` を使う（``pip install library-hiroba[ai]``）

入力した文章が外部に送られることはありません。通信はモデルを受け取るときだけです。

ライセンス: 使用するモデルのライセンスは配布元をご確認ください
（既定の Qwen2.5 は Apache-2.0）。
"""

from __future__ import annotations

__all__ = ["Ai", "ai"]


# ---------------------------------------------------------------------------
# モデルの名前
# ---------------------------------------------------------------------------
# ブラウザ側は同じモデルを精度違い（q8 / q4）で並べるため、名前に -q8 / -q4 が付く。
# Colab 側にその区別は無い。どちらの名前で呼ばれても動くよう、ここで受け止める。
#
#   共通の名前（これを使うのが推奨）… qwen05 / qwen15 / llmjp150m
#   ブラウザ固有の名前（そのまま通す）… qwen05-q8 / qwen05-q4 / qwen15-q4 / llmjp150m-q4
MODELS = {
    "qwen05": {
        "label": "Qwen2.5 0.5B（日本語が使えます・おすすめ）",
        "colab_id": "Qwen/Qwen2.5-0.5B-Instruct",
        "browser_key": "qwen05-q8",
        "browser_variants": ("qwen05-q8", "qwen05-q4"),
        "approx_mb": {"browser": 900, "colab": 1000},
    },
    "qwen15": {
        "label": "Qwen2.5 1.5B（日本語がより自然・重い）",
        "colab_id": "Qwen/Qwen2.5-1.5B-Instruct",
        "browser_key": "qwen15-q4",
        "browser_variants": ("qwen15-q4",),
        "approx_mb": {"browser": 1600, "colab": 3100},
    },
    "llmjp150m": {
        "label": "LLM-jp-3 150M（国産・とても軽い／文章は不自然です）",
        "colab_id": "llm-jp/llm-jp-3-150m-instruct3",
        "browser_key": "llmjp150m-q4",
        "browser_variants": ("llmjp150m-q4",),
        "approx_mb": {"browser": 255, "colab": 600},
    },
}

DEFAULT_MODEL = "qwen05"

# ブラウザ固有の名前 → 共通の名前
_VARIANT_TO_BASE = {
    variant: base for base, spec in MODELS.items() for variant in spec["browser_variants"]
}


def resolve(name: str | None) -> tuple[str, str]:
    """モデル名を「共通の名前」と「ブラウザに渡す名前」の組にする。

    どちらの書き方で呼ばれても受け付ける。共通の名前だけを渡された場合、
    ブラウザには推奨の精度（``browser_key``）を渡す。
    """
    if name is None:
        name = DEFAULT_MODEL
    name = str(name)
    if name in MODELS:
        return name, MODELS[name]["browser_key"]
    if name in _VARIANT_TO_BASE:
        # 精度まで指定された場合は、その指定を尊重してそのまま渡す
        return _VARIANT_TO_BASE[name], name
    raise ValueError(
        f"そのモデルは選べません: {name}"
        "（await ai.models() で選べるものを確認できます）"
    )


def _dtype_keyword(pipeline) -> str:
    """``pipeline()`` に数値の精度を渡すときのキーワード名。

    transformers 5 で ``torch_dtype`` は ``dtype`` に改名された。古い名前も
    まだ通るが、実行するたびに非推奨の警告が出る。Colab に入っている版が
    どちらでも警告なく動くよう、その版が受け付ける名前で渡す。
    """
    import inspect

    return "dtype" if "dtype" in inspect.signature(pipeline).parameters else "torch_dtype"


def in_browser() -> bool:
    """PyHiroba のワーカーの中にいるか。

    ``js`` が入るのは Pyodide だけで、``pyhirobaAsk`` を持つのは PyHiroba 本体だけ。
    """
    try:
        import js
    except ImportError:
        return False
    return hasattr(js, "pyhirobaAsk")


# ---------------------------------------------------------------------------


class Ai:
    """小さな言語モデルを動かす。PyHiroba と Colab で同じ使い方ができる。"""

    def __init__(self) -> None:
        self._pipe = None
        self._name: str | None = None

    async def models(self) -> list[dict]:
        """選べるモデルの一覧（名前と目安の通信量）。

        返す形はどちらの経路でも同じ ``[{"name", "label", "approxMB"}, …]``。
        通信量は環境で実際に違うため、その環境の値を返す。
        """
        where = "browser" if in_browser() else "colab"
        return [
            {"name": name, "label": spec["label"], "approxMB": spec["approx_mb"][where]}
            for name, spec in MODELS.items()
        ]

    async def load(self, model: str | None = None) -> str:
        """モデルを読み込む。初回だけ時間と通信量がかかる。"""
        base, browser_key = resolve(model)
        if in_browser():
            return await self._load_in_browser(browser_key)
        return self._load_with_transformers(base)

    async def ask(self, prompt: object, max_tokens: int | None = None) -> str:
        """文章を渡して、続きを書いてもらう。"""
        if in_browser():
            return await self._ask_in_browser(prompt, max_tokens)
        if self._pipe is None:
            await self.load()
        return self._ask_with_transformers(prompt, max_tokens)

    # --- ブラウザ経路（PyHiroba 本体との契約） -----------------------------
    #
    # 本体のワーカーが js.pyhirobaAsk(kind, argsJson) -> Promise<resultJson> を用意する。
    # やり取りは JSON 文字列だけ（Pyodide と JS の境界を単純に保つため）。
    # kind は本体の許可リストにある ai-load / ai-ask / ai-models の3つのみ。

    async def _call_host(self, kind: str, args_json: str):
        import json

        import js

        return json.loads(await js.pyhirobaAsk(kind, args_json))

    async def _load_in_browser(self, browser_key: str) -> str:
        import json

        result = await self._call_host("ai-load", json.dumps({"model": browser_key}))
        self._name = browser_key
        return result.get("message", "準備ができました")

    async def _ask_in_browser(self, prompt: object, max_tokens: int | None) -> str:
        import json

        if self._name is None:
            await self.load()
        result = await self._call_host(
            "ai-ask", json.dumps({"prompt": str(prompt), "max_tokens": max_tokens})
        )
        return result.get("text", "")

    # --- Colab 経路（transformers + torch） --------------------------------

    def _load_with_transformers(self, base: str) -> str:
        if self._pipe is not None and self._name == base:
            return "すでに準備できています"

        try:
            import torch
            from transformers import pipeline
        except ImportError as error:
            raise ImportError(
                "transformers と torch が必要です。次の行を先に実行してください:\n"
                "    !pip install -q library-hiroba[ai]"
            ) from error

        device = 0 if torch.cuda.is_available() else -1
        self._pipe = pipeline(
            "text-generation",
            model=MODELS[base]["colab_id"],
            device=device,
            **{_dtype_keyword(pipeline): torch.float16 if device == 0 else torch.float32},
        )
        self._name = base
        where = "GPU" if device == 0 else "CPU"
        return f"準備ができました（{MODELS[base]['label']}／{where}で動きます）"

    def _ask_with_transformers(self, prompt: object, max_tokens: int | None) -> str:
        # 生成の設定はブラウザ側と揃えてある。小さなモデルはばらつきを大きくすると
        # 意味の通らない文章になりやすいので、温度を下げ繰り返しを抑える。
        out = self._pipe(
            [{"role": "user", "content": str(prompt)}],
            max_new_tokens=max_tokens or 256,
            temperature=0.3,
            top_p=0.9,
            repetition_penalty=1.15,
            do_sample=True,
            return_full_text=False,
        )
        text = out[0]["generated_text"]
        # 会話形式で渡すと返り値も会話の並びになる。最後の発言を取り出す。
        if isinstance(text, list):
            text = (text[-1] or {}).get("content", "") if text else ""
        return str(text).strip()


ai = Ai()
