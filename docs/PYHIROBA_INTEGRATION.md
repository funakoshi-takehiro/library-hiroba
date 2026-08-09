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

- **`ui` 側は純 Python・標準ライブラリだけ**です（`_core` / `_css` / `_components` / `_forms` / `ui`）。閉じた校内ネットワークでも、追加の取得なしに動きます。この約束はテストで固定してあります（`tests/test_ai.py::test_ui_stays_dependency_free`）
- **`ai` は使われるまで読み込みません**。`from library_hiroba import ui` だけなら `_ai.py` は読み込まれません
- `_ai.py` はブラウザでは `js` しか使いません。`transformers` / `torch` を読み込むのは Colab 経路に入ったときだけです

## 2. `ai` が本体に求めるもの

`_ai.py` は、ブラウザにいるかどうかを **`js.pyhirobaAsk` があるか**で判断します（`js` が入るのは Pyodide だけ、`pyhirobaAsk` を持つのは PyHiroba 本体だけ）。素の Pyodide では Colab 経路に落ちます。

```js
// 本体がワーカーのグローバルに用意する
globalThis.pyhirobaAsk = async (kind, argsJson) => { /* … */ return resultJson }
```

- 引数も返り値も **JSON 文字列だけ**です（Pyodide と JS の境界を単純に保つため）
- `kind` は次の2つだけ使います。本体の許可リストに `ai-models` があっても、library-hiroba は呼びません（後述）

| `kind` | 渡す JSON | 期待する JSON | 読む値 |
|---|---|---|---|
| `ai-load` | `{"model": "qwen05-q8"}` | `{"message": "準備ができました（…）", "device": "webgpu"}` | `message`（無ければ「準備ができました」） |
| `ai-ask` | `{"prompt": "日本の四季について", "max_tokens": 64}` | `{"text": "…", "ms": 3700, "device": "webgpu"}` | `text`（無ければ空文字） |

`max_tokens` は指定が無いと `null` を渡します。本体側の既定（256）で扱ってください。

### モデルの名前

ブラウザ側は同じモデルを精度違いで並べるため名前に `-q8` / `-q4` が付きますが、Colab 側にその区別はありません。両方を受け付け、**本体には必ずブラウザ側の名前を渡します**。

| 利用者が書く名前 | 本体に渡る名前 | Colab で使う ID |
|---|---|---|
| `qwen05`（既定） | `qwen05-q8` | `Qwen/Qwen2.5-0.5B-Instruct` |
| `qwen05-q4` | `qwen05-q4` | `Qwen/Qwen2.5-0.5B-Instruct` |
| `qwen15` | `qwen15-q4` | `Qwen/Qwen2.5-1.5B-Instruct` |
| `llmjp150m` | `llmjp150m-q4` | `llm-jp/llm-jp-3-150m-instruct3` |

精度まで指定されたときは、その指定をそのまま尊重して渡します。一覧に無い名前は本体に届く前に `ValueError` にします。

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
