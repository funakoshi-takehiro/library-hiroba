# library-hiroba の機能一覧（0.8.1）

**同じコードが Google Colab と PyHiroba（ブラウザの中で動く Python）の両方で動く**、
という一点を土台にした教育向けライブラリ。入口は `ui` と `ai` の2つ。

README は「どう書くか」の案内、この文書は「何があるか」の一覧です。

---

## 1. `ui` — 画面をつくる

**依存ゼロ・純 Python。JavaScript を一切出力しません。** CSS だけで動き、PyHiroba の
サニタイザ（DOMPurify）を通しても表示が変わらないことをテストで固定しています。

### 見せる部品

| 入口 | 何が出るか |
| --- | --- |
| `ui.card(title, body, icon, footer)` | 説明カード |
| `ui.alert(message, kind, title)` | 注意書き（`info` / `success` / `warning` / `danger`） |
| `ui.badge(text, color)` | ラベル（`blue` / `green` / `red` / `amber` / `gray`） |
| `ui.stat(label, value, unit, icon)` | 数値の強調表示 |
| `ui.table(data, headers, caption)` | 表（辞書のリストでもリストのリストでも） |
| `ui.progress(value, max, label, show_value)` | 進捗バー（ARIA つき） |
| `ui.quiz(question, choices, answer, explanation)` | 択一クイズ。**正誤の表示は CSS だけ**で動く |
| `ui.reveal(content, summary)` | 折りたたみ（`<details>`） |
| `ui.thinking(text)` | 「考え中」の明滅 |
| `ui.html(raw, css, scoped)` | 生の HTML ＋ その部品だけに効く CSS |

**値の場所に部品を入れられます。** `ui.card("結果", ui.table(scores))` のように書くと、
中の部品が要る CSS まで一緒に出ます。

### 並べる

| 入口 | |
| --- | --- |
| `ui.stack(*items, gap)` | 縦に積む |
| `ui.columns(*items, widths, gap)` | 横に並べる（狭い画面では折り返す） |
| `ui.show(*items)` | セルの途中で表示する |

3つとも、**リスト1つでもジェネレータでも**受け取ります
（`ui.columns(parts)` / `ui.columns(ui.badge(c) for c in "ABC")`）。
`gap` と `widths` の長さには**単位が必要**です（単位が無いと CSS ごと捨てられるため）。

### 会話

| 入口 | |
| --- | --- |
| `ui.chat(messages, names)` | 渡された分をその場で吹き出しにする |
| `ui.conversation(messages, names)` | ためていく入れ物。`say` / `reply` / `note` / `clear` / `messages` |

### 入力

| 入口 | |
| --- | --- |
| `ui.field(name, label, placeholder, kind, choices, default)` | 入力欄。`kind` は `text` / `number` / `choice` / `multiline` |
| `ui.form(handler, *fields, submit_label, title, clear_on_submit, pending)` | フォーム |
| `ui.get_form(form_id)` | 本体から引き当てる口（登録は 64 件まで） |

`handler` は**ふつうの関数・`async def`・`yield` で書いたもの**のどれでもよく、
`yield` するものは届くたびに表示が差し替わります（AI の答えを書きかけから見せる経路）。

**フォームは3つの経路を自動で使い分けます。**

| 環境 | 何を使うか |
| --- | --- |
| Colab | ipywidgets の部品 |
| PyHiroba | 静的な HTML ＋ 本体からの呼び戻し（`ui.get_form`） |
| 素の Python | `input()` で順番に聞く |

容器（`ui.stack` など）に入れても動きます。ただし Colab では入力欄を生かすために
**容器の中身を1つずつ出す**ので、容器の間隔や横並びは効きません。

Colab では ipywidgets の部品を使うため、こちらの見た目と ipywidgets の決め打ち
（入力欄 28px・名前の欄 80px）がぶつかります。打ち消しは `_css.py` の `widgets` に
あり、実際に描いて測り直すには `python tools/check_widget_css.py` を使います
（PyHiroba 側の HTML と同じ 36px・ボタンは伸びない、に揃えてあります）。

### そのほか

`ui.use_web_font(enabled)` … 書体を Google Fonts から取るかどうか。**既定は取りません**
（表示のたびに閲覧者の IP が Google に渡るため）。既定のままでも PyHiroba では
ページ側が同じ書体を持っているので見た目が揃います。

---

## 2. `ai` — 小さな言語モデルを動かす

PyHiroba では本体の橋（`js.pyhirobaAsk`）、Colab では transformers + torch。
**使われるまで読み込まれない**ので、`ui` だけの環境に torch は入りません。

| 入口 | |
| --- | --- |
| `ai.load(model)` / `ai.is_loaded()` / `ai.models()` | 読み込みと状態、選べる一覧 |
| `ai.ask(prompt, max_tokens)` | 1問1答 |
| `ai.stream(prompt, max_tokens)` | 書けたところから少しずつ（**未対応の環境では自動で全文に落ちる**） |
| `ai.talk(keep, max_tokens, names, instruction)` | 記憶つきの往復 |
| `ai.embed(texts, model)` | 文をベクトルにする |
| `ai.search(query, documents, top_k)` | 意味で探す（RAG の土台） |
| `ai.environment()` / `ai.recommend()` / `ai.load("auto")` | 端末を調べて、動くものを勧める |

`ai.talk()` が返すもの … `ask` / `stream` / `form` / `clear` / `messages`。
記憶の受け渡し・モデルが書き足した続きの切り落とし・逐次表示の組み立て・
入力欄つきフォームまでを、これ1つが持ちます。往復が重なっても、答えは
**自分の質問の下**に入ります。

### 選べるモデル（軽い順）

| 名前 | ブラウザ | Colab | |
| --- | --- | --- | --- |
| `llmjp150m` | 270MB | 600MB | 国産・とても軽い（WebGPU 無しでも動く） |
| `qwen05`（既定） | 520MB | 1.0GB | 日本語が使える |
| `qwen35_08` | 560MB | 1.8GB | **この中でいちばん新しく、軽いのに賢い** |
| `qwen3_06` | 620MB | 1.5GB | `qwen05` より新しい |
| `qwen15` | 1.8GB | 3.1GB | 日本語がより自然 |
| `qwen3_17` | 2.2GB | 3.4GB | おまかせで選ばれるうちでは最上 |
| `qwen3_4b` | 2.9GB | 8.1GB | **いちばん賢い。名前を書いたときだけ動く** |

埋め込みは `minilm`（多言語 MiniLM・384次元・ブラウザ 118MB）。

`qwen3_4b` は `ai.load("auto")` でも `ai.recommend()` でも**選ばれません**。ブラウザでは
2.9GB を生徒一人ひとりが落とすことになり、校内の回線で配ってよいかは教室を知っている
人が決めることだからです。

Colab 側のモデルは **Hugging Face のコミットで固定**してあります（`colab_revision`）。
固定しないと、上流が更新された日から「去年と同じ教材なのに答えが変わる」ことが起きます。

### 本体（PyHiroba）との対応状況

`js.pyhirobaFeatures` の目印で判定します。

| 目印 | 使う場所 | 本体 | library |
| --- | --- | --- | --- |
| `ai-load` / `ai-ask`（必須） | `ai.load()` / `ai.ask()` | ✅ | ✅ |
| `ai-probe` | `ai.recommend()` / `load("auto")` | ✅ | ✅ |
| `forms` | `ui.form()` / `talk.form()` | ✅ | ✅ |
| `ai-embed` | `ai.embed()` / `ai.search()` | ✅ | ✅ |
| `ai-stream` | `ai.stream()` の逐次表示 | ⬜ 未実装 | ✅ 受け側は用意済み |

`ai-stream` が無いあいだは `ai-ask` に自動で落ちるので、利用者のコードは書き換え不要です。

---

## 3. 全体で守っていること

| | |
| --- | --- |
| **黙って間違わない** | 例外にならず、それらしい答えが出る書き方を止める。いちばん重い不具合として扱う |
| **環境で割れない** | 同じコードが Colab と PyHiroba で違う動きをしないこと |
| **原因が読める文言** | どの引数が悪いのか、どう書けばよいのかを日本語で言う |
| **サニタイザ生存** | Colab で動いて PyHiroba で消える、が起きないこと（`ui.html()` は書いた時点で止める） |
| **JavaScript を出さない** | 全部品の出力に `<script>` も `on*` 属性も無いことをテストで固定 |
| **外部と通信しない** | 書体の取得（既定 off）以外、表示で通信は発生しない |

資源の上限 … 埋め込み 10,000 件（1回の送信は 256 件ずつ）／フォームの登録 64 件／
逐次出力 300 秒。

---

## 4. 教材（そのまま Colab で開けます）

| ノートブック | |
| --- | --- |
| `notebooks/chat.ipynb` | AI とチャットする |
| `notebooks/book_search.ipynb` | 意味で探す蔵書検索 |
| `notebooks/demo_ai.ipynb` | `ai` のひととおり |
| `notebooks/demo_colab.ipynb` | `ui` の部品を並べて見る |
| `notebooks/html_css_recipes.ipynb` | `ui.html()` の作例 |
| `examples/school_rules_bot.ipynb` | 校則をもとに答える RAG ボット |

## 5. 関連する文書

| | |
| --- | --- |
| [`PYHIROBA_INTEGRATION.md`](PYHIROBA_INTEGRATION.md) | 本体との契約。モデルを増やすときの手順もここ |
| [`PYHIROBA_STATUS.md`](PYHIROBA_STATUS.md) | いまどこまで揃っているか（リリースごとに書き換える） |
| [`PYHIROBA_FORMS.md`](PYHIROBA_FORMS.md) | フォームを本体から動かす仕組み |
| [`RELEASING.md`](RELEASING.md) | 公開の手順 |
