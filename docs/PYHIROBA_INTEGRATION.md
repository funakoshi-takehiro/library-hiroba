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
- **サニタイザに落とされるものは、ライブラリ側でも受け付けません**。部品の出力にそれらが含まれないことは以前から `tests/sanitize_check.py` で固定していますが、0.4.0 からは唯一エスケープしない経路である `ui.html()` も、`<script>` などのタグ・`on*` 属性・`javascript:` URL を見つけた時点で `ValueError` にします。本体のサニタイザが無い Colab で書いて、PyHiroba に載せて初めて消えているのに気付く、という順序を避けるためです。禁止タグの一覧は本体側と揃える必要があるので、変えるときは連絡してください（`src/library_hiroba/_components.py` の `DANGEROUS_TAGS`）
- **`ui` が使う標準ライブラリに `threading` が入りました**（0.5.1）。使うのは Colab・Jupyter の ipywidgets 経路だけです。Colab はセルの実行が終わっているあいだイベントループを回しておらず、ボタンの押下から予約したタスクが走らないため、自前のループを別スレッドで回しています。**PyHiroba には IPython も ipywidgets も無いのでこの経路に入らず、Pyodide 上でスレッドを作ることはありません。** `import threading` 自体も関数の中まで遅らせてあります
- **`ai` は使われるまで読み込みません**。`from library_hiroba import ui` だけなら `_ai.py` は読み込まれません
- `_ai.py` はブラウザでは `js` しか使いません。`transformers` / `torch` を読み込むのは Colab 経路に入ったときだけです

## 2. `ai` が本体に求めるもの

`_ai.py` は、ブラウザにいるかどうかを **`js.pyhirobaAsk` があるか**で判断します（`js` が入るのは Pyodide だけ、`pyhirobaAsk` を持つのは PyHiroba 本体だけ）。素の Pyodide では Colab 経路に落ちます。

```js
// 本体がワーカーのグローバルに用意する
globalThis.pyhirobaAsk = async (kind, argsJson) => { /* … */ return resultJson }
```

- 引数も返り値も **JSON 文字列だけ**です（Pyodide と JS の境界を単純に保つため）
- `kind` は `ai-load` と `ai-ask` の2つが必須です。`ai-ask-start` / `ai-ask-next`（書けたところから返す）と `ai-probe`（端末を調べる）は任意で、いずれも未対応なら自動的に落ちます（後述）。本体の許可リストに `ai-models` があっても、library-hiroba は呼びません（後述）

| `kind` | 渡す JSON | 期待する JSON | 読む値 |
|---|---|---|---|
| `ai-load` | `{"model": "qwen05-q8"}` | `{"message": "準備ができました（…）", "device": "webgpu"}` | `message`（無ければ「準備ができました」） |
| `ai-ask` | `{"prompt": "日本の四季について", "max_tokens": 64}` | `{"text": "…", "ms": 3700, "device": "webgpu"}` | `text`（無ければ空文字） |

`max_tokens` は指定が無いと `null` を渡します。本体側の既定（256）で扱ってください。

### 対応している機能を名乗る（`pyhirobaFeatures`）

本体が対応している機能を、ワーカーのグローバルに文字列で置いてください。

```js
self.pyhirobaFeatures = 'forms,ai,ai-probe'
```

**これが無いと library-hiroba は本体の版を知る手段がありません。** 実際に事故が起きました。0.5.0〜0.5.1 の `ai.talk().form()` は `in_browser()`（＝`pyhirobaAsk` があるか）で「フォームが使えるか」を判断しており、本体がフォームに対応したあとも「PyHiroba では動きません」と警告を出し続けていました。`pyhirobaAsk` は AI の受け渡しがあるかしか答えず、**AI が動くこととフォームが動くことは別**です。

- 読み方は「,」区切りの**完全一致**です。前後の空白は落とします
- 名乗っていない機能は「未対応」として扱います。ただし**この変数自体が無い本体**は「名乗らない古い本体」とみなし、これまでどおり呼んでみて落ちたら諦める形に戻ります（対応済みなのに名乗っていない本体を、機能無しに落とさないため）
- library-hiroba 側は `_ai.host_features()` / `_ai.host_supports("forms")` で読みます

いま見ている名前は次のとおりです。

| 名前 | 付けると |
|---|---|
| `forms` | `ai.talk().form()` が注意書き無しで出ます |
| `ai-stream` | `ai.stream()` が `ai-ask-start` / `ai-ask-next` を使います。無ければ `ai-ask` で全文を一度に返します（下記） |

`ai` と `ai-probe` も受け取れる形にしてありますが、いまは判断に使っていません（`ai-probe` は返事の中身で未対応が分かるためです）。将来のために名乗っていただいて構いません。

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

### 文をベクトルにする（`ai-embed`）

`ai.embed()` / `ai.search()` が使います。**対応は目印で判定します** — `pyhirobaFeatures` に `ai-embed` が無ければ、library 側で「まだ対応していません」と伝えて呼びません（版は見ません）。

| `kind` | 渡す JSON | 期待する JSON |
|---|---|---|
| `ai-embed` | `{"model": "minilm", "texts": ["…", "…"]}` | `{"vectors": [[…384…]], "dim": 384, "device": "wasm", "model": "minilm"}` |

- **ベクトルは L2 正規化済み**（mean pooling + normalize）でお願いします。内積がそのままコサイン類似度になる前提で `search()` を作っています。**library 側でも1本だけ長さを検算します**（正規化されていないと近い順が静かに狂い、気付けないため）
- **すべてのベクトルの次元（384）を確かめます**（0.6.1 から）。配布元を版で固定していないため、上流でモデルが差し替わると黙って別のベクトルが返ります。1本でも長さが違えば、理由を添えて止めます。`dim: 384` を返し続けていただければ何も起きません
- ベクトルの要素に数でないものが混じっていた場合も、本体側の不具合と分かる文言で止めます
- `texts` が空なら `{"vectors": [], …}` を返してください
- **一度に渡すのは 256 件まで**にしてあります。それ以上は library 側で分けて複数回呼びます。素通しすると、同じコードが PyHiroba で失敗して Colab で成功する、という食い違いになるためです
- 断るとき（Promise の reject）の理由は日本語でお願いします。`_call_host` がそれを包んで利用者に見せます

使うモデルは1つだけです。**チャットの `MODELS` とは別の一覧**（`EMBED_MODELS`）に置いてあり、`ai.load()` には通しません。

| キー | 本体が読む ONNX | Colab で使う id | 次元 |
|---|---|---|---|
| `minilm`（既定） | `Xenova/paraphrase-multilingual-MiniLM-L12-v2` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 |

> **int8（`model_quantized.onnx` / 118MB）を使ってください。** このモデルも q4 のほうが大きくなります（399MB）。語彙が 250037 と大きく、q4 では埋め込み（`Gather`）が fp32 のまま残るためで、Qwen3 0.6B と同じ理由です。
>
> Colab 側は `sentence-transformers` を使わず、`transformers` + `torch` で mean pooling と L2 正規化を自前で行っています（`sentence-transformers` は `transformers>=5` を要求し、scikit-learn と scipy を連れてくるため）。**本体と同じ処理なので、両経路で同じ意味のベクトルになります**（int8 と fp32 の差で値は完全一致しません。索引と検索は同じ環境で作る前提です）。

### 端末を調べる（任意）

`ai.recommend()` と `ai.load("auto")` は、その端末で実用になるモデルのうちいちばん良いものを選びます。WebGPU の無い端末に 1.7B を読ませると画面が固まり、逆に動く端末で 150M を使うと答えが不自然になるためです。**対応は任意です** — 本体が知らなければ「調べられなかった」として、環境によらず既定の `qwen05` に落ちます。

| `kind` | 渡す JSON | 期待する JSON |
|---|---|---|
| `ai-probe` | `{}` | `{"webgpu": true, "memoryGB": 8, "cores": 12, "storageMB": 40000, "browser": "Chrome 120"}` |

- **`webgpu` だけが必須**です。これが入っていない返事は「答えられなかった」とみなします（`{}` を返せば未対応と伝わるので、**そのために何かを実装する必要はありません**）
- ほかの4つは省略できます。省いた項目は判断に使いません。ただし `memoryGB` が無いときは、外れたときの影響が大きいので既定より重いモデルは選びません
- 数値以外（文字列など）が入っていた項目は、無かったものとして扱います
- 調べるのは端末の余力だけです。**利用者の入力や閲覧履歴に類するものは送らないでください**

実装はこれで足ります。

```js
const adapter = navigator.gpu ? await navigator.gpu.requestAdapter() : null
const room = await navigator.storage?.estimate?.()
return JSON.stringify({
  webgpu: !!adapter,
  memoryGB: navigator.deviceMemory ?? null,       // Firefox / Safari には無い
  cores: navigator.hardwareConcurrency ?? null,
  storageMB: room ? Math.floor((room.quota - room.usage) / 1048576) : null,
  browser: "Chrome 120",                          // 表示に使うだけ。省略可
})
```

`requestAdapter()` は WebGPU が無効な環境で `null` を返します（例外にはなりません）。`navigator.gpu` 自体が無いこともあるので、上のように先に確かめてください。

### モデルの名前

ブラウザ側は同じモデルを精度違いで並べるため名前に `-q8` / `-q4` が付きますが、Colab 側にその区別はありません。両方を受け付け、**本体には必ずブラウザ側の名前を渡します**。

| 利用者が書く名前 | 本体に渡る名前 | 本体が読む ONNX | Colab で使う ID |
|---|---|---|---|
| `qwen05`（既定） | `qwen05-q8` | `onnx-community/Qwen2.5-0.5B-Instruct` | `Qwen/Qwen2.5-0.5B-Instruct` |
| `qwen05-q4` | `qwen05-q4` | 同上（q4 の重み） | `Qwen/Qwen2.5-0.5B-Instruct` |
| `qwen15` | `qwen15-q4` | `onnx-community/Qwen2.5-1.5B-Instruct` | `Qwen/Qwen2.5-1.5B-Instruct` |
| `qwen3_06` | `qwen3_06-q8` | `onnx-community/Qwen3-0.6B-ONNX` | `Qwen/Qwen3-0.6B` |
| `qwen3_06-q4` | `qwen3_06-q4` | 同上（q4 の重み） | `Qwen/Qwen3-0.6B` |
| `qwen3_17` | `qwen3_17-q4` | `onnx-community/Qwen3-1.7B-ONNX` | `Qwen/Qwen3-1.7B` |
| `llmjp150m` | `llmjp150m-q4` | `onnx-community/llm-jp-3-150m-instruct2-ONNX` | `llm-jp/llm-jp-3-150m-instruct2` |

精度まで指定されたときは、その指定をそのまま尊重して渡します。一覧に無い名前は本体に届く前に `ValueError` にします。

> **`qwen3_06` だけ推奨が q8 です**（0.4.0 で q4 から変更）。このモデルは 4bit のほうが**大きく**（q4 877MB / q8 589MB）、精度も 8bit のほうが上だからです。逆に見えますが、`onnx-community` の q4 は MatMul の重みだけを 4bit にし、埋め込み（`Gather` 演算）を fp32 のまま残すためです。Qwen3 0.6B は語彙が 151936 と大きく、埋め込みだけで全体の 26%（156M パラメータ＝fp32 で 622MB）を占めるので、そこが残ると 4bit にした分を打ち消して上回ります。「4bit なら軽いはず」で戻さないよう、テストで固定してあります（`tests/test_ai.py::test_the_recommended_precision_is_not_the_biggest_download`）。他のモデルは埋め込みの比率が小さいか q8 が用意されていないため、q4 のままです。

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

### `ai.talk()` について（本体側の対応は不要です）

0.5.0 で足した `ai.talk()` は、会話の記憶・モデルが書き足した続きの切り落とし・逐次表示の組み立てを library-hiroba 側で行うだけの入れ物です。**本体に求めるものは増えません。** 内部で呼ぶのは今までと同じ `ai-ask`（と、あれば `ai-ask-start` / `ai-ask-next`）で、記憶は「これまでの会話」を1つの文章に組み直して `ai-ask` の `prompt` に載せる形で渡します。本体から見ると、少し長い prompt が来るだけです。

`talk.form()` は `ui.form()` をそのまま使います。本体は 2026-08-09（`df6d049`）でフォームに対応したため、**そのままで動きます**。それ以前の本体で開いた場合だけ、押しても何も起きないフォームを黙って出さないよう注意書きを添えます。出し分けは次節の `pyhirobaFeatures` を見て行っています。

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
| 環境判定が実際の速さと釣り合うか | GPU の有る／無い Colab の両方で `python tools/check_ai_colab.py --model auto` |
| 本体の `ai-probe` が期待どおりか | PyHiroba のセルで `await ai.recommend()`。未実装なら「調べられなかった」と出る |
