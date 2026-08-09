# PyHiroba に library-hiroba を組み込むときの取り決め

PyHiroba 本体は library-hiroba を同梱（vendoring）して配ります。本体側が知っておく必要のあることを、この1枚にまとめます。

- 同梱するファイルの一覧（増減したらここを更新し、本体側に連絡します）
- `ai` が本体に求める受け渡し（`js.pyhirobaAsk`）の形
- フォームの受け渡しは [`PYHIROBA_FORMS.md`](PYHIROBA_FORMS.md) にあります

---

## 1. 同梱するファイル

`src/library_hiroba/` の中身をそのまま並べれば `import library_hiroba` できます。wheel を作る必要はありません。

| ファイル | 役割 | 無いとどうなるか |
|---|---|---|
| `__init__.py` | 入口。`ui` と `ai` を、使われたときに読み込む | import できません |
| `ui.py` | UI 部品の入口（`ui.card` などをまとめて公開） | `ui` が使えません |
| `_core.py` | エスケープと `Widget` の土台 | `ui` が使えません |
| `_css.py` | 配色・書体などの CSS | 部品が素の見た目になります |
| `_components.py` | カード・クイズ・表などの部品 | `ui` が使えません |
| `_forms.py` | 入力フォーム（`ui.form` / `ui.field` / `ui.get_form`） | `ui.form` が使えません |
| `_ai.py` | 小さな言語モデル（`ai`） | `ai` が使えません（`ui` は動きます） |
| `py.typed` | 型情報を同梱している印 | 型チェックの精度が落ちるだけ |

### 0.3.0（改名）での変更点

| 変更 | 内容 |
|---|---|
| パッケージ名 | `ui_hiroba` → `library_hiroba`（配布名は `ui-hiroba` → `library-hiroba`） |
| 入口 | `import ui_hiroba as ui` → `from library_hiroba import ui`（互換は残していません） |
| ファイルの移動 | もとの `__init__.py` の中身は `ui.py` へ。`__init__.py` は入口だけになりました |
| ファイルの追加 | `_ai.py` |

### 守っていること

- **`ui` 側は純 Python・標準ライブラリだけ**です（`_core` / `_css` / `_components` / `_forms` / `ui`）。閉じた校内ネットワークでも、**パッケージの追加取得なしに**動きます。この約束はテストで固定してあります（`tests/test_ai.py::test_ui_stays_dependency_free`）
- **書体は取りに行きません**。CSS は `font-family: 'Zen Kaku Gothic New', system-ui, sans-serif` と名前で指定するだけです。PyHiroba は出力をページと同じ document に挿すため、**本体がこの書体を読み込んでいれば、それだけで揃います**。本体側で読み込んでいない場合は `system-ui` になるので、揃えたいときは本体のページ側で読み込んでください（library-hiroba 側では取得しません）
  - 以前は CSS の先頭に Google Fonts の `@import` を入れていましたが、外しました。PyHiroba では本体が持っているぶん不要で、実際に効くのは Colab（隔離 iframe でページの書体が届かない）だけです。そちらは PyHiroba と揃っている必要がない一方、表示のたびに Google へ通信が起き閲覧者の IP が渡るため、既定では行いません。Colab で揃えたい利用者は `ui.use_web_font(True)` を呼べます
  - 取得先が増えていないことはテストで固定してあります（`tests/test_components.py::test_nothing_is_fetched_by_default`）
- **`ai` は使われるまで読み込みません**。`from library_hiroba import ui` だけなら `_ai.py` は読み込まれません
- `_ai.py` はブラウザでは `js` しか使いません。`transformers` / `torch` を読み込むのは Colab 経路に入ったときだけです

## 2. `ai` が本体に求めるもの

`_ai.py` は、ブラウザにいるかどうかを **`js.pyhirobaAsk` があるか**で判断します（`js` が入るのは Pyodide だけ、`pyhirobaAsk` を持つのは PyHiroba 本体だけ）。素の Pyodide では Colab 経路に落ちます。

```js
// 本体がワーカーのグローバルに用意する
globalThis.pyhirobaAsk = async (kind, argsJson) => { /* … */ return resultJson }
```

- 引数も返り値も **JSON 文字列だけ**です（Pyodide と JS の境界を単純に保つため）
- `kind` は `ai-load` と `ai-ask` の2つが必須で、`ai-ask-start` / `ai-ask-next` は任意です（後述）。本体の許可リストに `ai-models` があっても、library-hiroba は呼びません（後述）

| `kind` | 渡す JSON | 期待する JSON | 読む値 |
|---|---|---|---|
| `ai-load` | `{"model": "qwen05-q8"}` | `{"message": "準備ができました（…）", "device": "webgpu"}` | `message`（無ければ「準備ができました」） |
| `ai-ask` | `{"prompt": "日本の四季について", "max_tokens": 64}` | `{"text": "…", "ms": 3700, "device": "webgpu"}` | `text`（無ければ空文字） |

`max_tokens` は指定が無いと `null` を渡します。本体側の既定（256）で扱ってください。

### 書けたところから返す（任意）

`ai.stream()` は答えを少しずつ受け取ります。**対応は任意です** — 下の2つを本体が知らなければ、自動的に `ai-ask` に落ちて全文が一度に返ります。利用者のコードは書き換え不要です。

| `kind` | 渡す JSON | 期待する JSON |
|---|---|---|
| `ai-ask-start` | `{"prompt": "…", "max_tokens": 64}` | `{"id": "任意の文字列"}` |
| `ai-ask-next` | `{"id": "…"}` | `{"text": "次に書けたぶん", "done": false}` |

- `ai-ask-next` は、次が書けるまで待ってから返してください（空文字を返し続けると無駄に往復します）
- 最後の呼び出しで `"done": true` を返します。`text` に残りが入っていても構いません
- `id` を返さない、または `ai-ask-start` で失敗した場合、library-hiroba は `ai-ask` に切り替えます。**未対応であることを伝えるために、わざわざ何かを実装する必要はありません**
- `<think>…</think>` はライブラリ側で取り除きます。チャンクの境目で割れていても大丈夫なので、本体は分割位置を気にしなくて構いません

### モデルの名前

ブラウザ側は同じモデルを精度違いで並べるため名前に `-q8` / `-q4` が付きますが、Colab 側にその区別はありません。両方を受け付け、**本体には必ずブラウザ側の名前を渡します**。

| 利用者が書く名前 | 本体に渡る名前 | 本体が読む ONNX | Colab で使う ID |
|---|---|---|---|
| `qwen05`（既定） | `qwen05-q8` | `onnx-community/Qwen2.5-0.5B-Instruct` | `Qwen/Qwen2.5-0.5B-Instruct` |
| `qwen05-q4` | `qwen05-q4` | 同上（q4 の重み） | `Qwen/Qwen2.5-0.5B-Instruct` |
| `qwen15` | `qwen15-q4` | `onnx-community/Qwen2.5-1.5B-Instruct` | `Qwen/Qwen2.5-1.5B-Instruct` |
| `qwen3_06` | `qwen3_06-q4` | `onnx-community/Qwen3-0.6B-ONNX` | `Qwen/Qwen3-0.6B` |
| `qwen3_06-q8` | `qwen3_06-q8` | 同上（q8 の重み） | `Qwen/Qwen3-0.6B` |
| `qwen3_17` | `qwen3_17-q4` | `onnx-community/Qwen3-1.7B-ONNX` | `Qwen/Qwen3-1.7B` |
| `llmjp150m` | `llmjp150m-q4` | `onnx-community/llm-jp-3-150m-instruct2-ONNX` | `llm-jp/llm-jp-3-150m-instruct2` |

精度まで指定されたときは、その指定をそのまま尊重して渡します。一覧に無い名前は本体に届く前に `ValueError` にします。

**右の2列は同じモデルの別形式でなければいけません。** 本体が別の変換元を選ぶと、利用者は同じ名前を書いたのに環境ごとに違うモデルが動きます。取り違えを防ぐため、両方を `_ai.py` の `MODELS`（`browser_repo` と `colab_id`）に書き、名前が一致することをテストで確かめています（`tests/test_ai.py::test_both_paths_load_the_same_model`）。

> `llmjp150m` が **instruct3 ではなく instruct2** なのは、ONNX に変換されているのが instruct2 だけだからです。Colab だけ instruct3 にすると上記のずれが起きます。150M では両者の差はほとんどないため、揃えるほうを採りました。

### 考えている途中を見せない（Qwen3 系）

`qwen3_06` と `qwen3_17` は、答えの前に `<think>…</think>` で考えを書きます。授業では答えだけ見えればよいので、**本体側でも次の2つをお願いします**。

1. チャットテンプレートを当てるとき `enable_thinking: false` を渡す
2. 生成された文字列から `<think>…</think>` を取り除いてから返す

`_ai.py` は本体から受け取った文字列にも同じ削り取りを通します（`strip_thinking`）。**本体が忘れても利用者に見える結果は変わりません**が、1 をしないと考えるぶんだけ待ち時間と字数が無駄になります。字数が尽きて `</think>` が来なかった場合は、考えの途中を見せずに空文字列を返します。

### モデルを増やすとき

読めるモデルの幅は**ブラウザ側で決まります**。Colab は Hugging Face のほぼ何でも読めますが、ブラウザ（transformers.js）は **ONNX に変換済みのものしか読めない**ためです。増やすときは次の順で確かめてください。

1. ONNX 版があるか。`https://huggingface.co/models?other=onnx` を候補名で検索します
2. 元の PyTorch 版があるか（Colab 用）
3. 量子化した重みの大きさ。校内の回線で配れる範囲か
4. ライセンス。学校で使える条件か

**4つそろって初めて追加できます。** そろわないものを入れると「同じコードが両方で動く」が崩れます。

ONNX 版が無いモデルをどうしても使いたい場合は、自分で変換して配布する必要があります。

```bash
pip install "optimum[onnxruntime]"
optimum-cli export onnx --model llm-jp/llm-jp-3-440m-instruct3 --task text-generation-with-past out/
```

変換した重みは本体から取得できる場所に置いてください。この作業をしない限り、`MODELS` に足しても**ブラウザでは読み込みに失敗します**。

#### LLM-jp の現状（2026-08 時点）

`llm-jp-3` で ONNX 版が公開されているのは **150M の instruct2 だけ**です。440M・980M・1.8B・3.7B・13B と、instruct3 系にはいずれも変換版がありません。そのため、**上の変換を自分で行わない限り、LLM-jp を 150M より増やすことはできません**。

### `ai-models` を呼ばない理由

`await ai.models()` は、本体に聞かずに library-hiroba 側の表から作ります。本体の一覧をそのまま返すと、**同じコードなのに環境によって選べる名前が変わって**しまうためです。返す形は両方の経路で同じ `[{"name", "label", "approxMB"}, …]` で、`approxMB` だけがその環境の実際の値になります。

モデルを増減するときは、`_ai.py` の `MODELS` と本体の一覧の両方を更新してください。

## 3. フォームから `ai` を呼ぶ場合

`ai.ask()` は `async` なので、フォームの `handler` は `async def` になります。本体が `submit()` を呼ぶときは、返り値が待つもの（awaitable）かどうかを見て `await` してください。詳しくは [`PYHIROBA_FORMS.md`](PYHIROBA_FORMS.md) の 5-1 にあります。

## 4. 確かめ方

| 確かめたいこと | やり方 |
|---|---|
| 同梱した形で import できるか | `src/library_hiroba/` をコピーしたディレクトリで `python -c "from library_hiroba import ai, ui"` |
| `ui` が標準ライブラリだけで動くか | `pytest tests/test_ai.py::test_ui_stays_dependency_free` |
| 本体との受け渡しの形 | `pytest tests/test_ai.py`（`js.pyhirobaAsk` を偽物に差し替えて確かめています） |
| Colab 経路が実際に動くか | `pip install "library-hiroba[ai]"` のうえで `python tools/check_ai_colab.py` |
