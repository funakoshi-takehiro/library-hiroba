# library-hiroba

Google Colab と PyHiroba で、同じコードが同じように動く教育向けのライブラリです。次の2つのモジュールで構成されています。

| モジュール | できること |
|---|---|
| `ui` | カード・クイズ・進捗バーといったコンポーネントを、ノートブックのセル出力に表示します |
| `ai` | LLM を、その場（ブラウザまたはノートブック）で動かします |

## インストール

Google Colab と Jupyter:

```
!pip install library-hiroba
```

Google Colab で `ai` も使うときは、追加の依存（transformers と torch）を含めます。

```
!pip install "library-hiroba[ai]"
```

PyHiroba では `import library_hiroba` で使えます。`ai` の実行はブラウザ側の経路を使うため、追加のインストールは要りません。

読み込みは次のように書きます。

```python
from library_hiroba import ai, ui
```

## 特徴

用意されたコンポーネントに加えて、HTML と CSS を自由に書けます。教材に必要な見た目の多くは、この2つで作れます。

```python
ui.html('<div class="fukidashi">まずは print() を試してみよう</div>',
        css=".fukidashi { border: 2px solid var(--hui-accent); border-radius: 14px; padding: 10px 16px; }")
```

CSS が届く範囲はそのコンポーネントの内側に限られるため、クラス名を気軽に付けてもページの他の部分に影響しません。ふきだし、手順ステップ、単語カード、横棒グラフといった見た目も、この方法で作れます。

そのほかの特徴は次のとおりです。

| 項目 | 内容 |
|---|---|
| 動作環境 | セル最後の式を `_repr_html_()` で表示する共通のしくみに乗るため、Google Colab と PyHiroba で表示が一致します |
| 実装方式 | 表示も操作も HTML と CSS で完結します（クイズの正誤表示は `:checked`、開閉は `<details>`） |
| 依存関係 | `ui` は純 Python で、依存ライブラリがありません。配布物は `py3-none-any` の wheel で、Google Colab の pip でも Pyodide の micropip でも取得できます（`ai` を Google Colab で使うときは追加の依存が必要です） |
| 見た目 | 配色・書体・角丸を PyHiroba 本体のデザインに合わせています |
| 配慮 | 本文と状態色は WCAG 4.5:1 以上です（アクセント色を塗ったボタンの白文字は 3.87:1 で、UI コンポーネントの基準 3:1 を満たします）。アニメーションは `prefers-reduced-motion` に従います |

## コンポーネント一覧

| コンポーネント | 例 |
|---|---|
| 説明カード | `ui.card("今日の目標", "本文", footer="ヒント")` |
| ヒント・注意 | `ui.alert("メッセージ", kind="warning", title="よくあるまちがい")`（kind: `info` / `success` / `warning` / `danger`） |
| 選択式クイズ | `ui.quiz("問題", choices=[128, 256, 512], answer=256, explanation="解説")`（`answer` は値で指定します） |
| 答えの開閉 | `ui.reveal("答えは42", summary="答えを見る")` |
| 進捗バー | `ui.progress(7, max=10, label="練習問題")` |
| 数値タイル | `ui.stat("正答率", 85, unit="%")` |
| 横並び配置 | `ui.columns(ui.stat("得点", 90), ui.stat("順位", 3), widths=[2, 1])` |
| バッジ | `ui.badge("重要", color="red")`（color: `blue` / `green` / `red` / `amber` / `gray`） |
| テーブル | `ui.table([{"名前": "佐藤", "得点": 90}], caption="結果")` |
| 自由 HTML/CSS | `ui.html('<div class="x">…</div>', css=".x { color: hotpink; }")` |
| 入力フォーム | `ui.form(handler, ui.field("question", label="質問"))` |
| 考え中の表示 | `ui.thinking("考え中")`（`ui.form()` が送信中に自動で出します） |
| 会話の表示 | `ui.chat([{"role": "user", "content": "…"}, {"role": "assistant", "content": "…"}])` |

複数のコンポーネントは次のようにまとめます。

```python
ui.stack(ui.card("目標", "..."), ui.progress(3, max=10))   # 縦に積む
ui.columns(ui.stat("得点", 90), ui.stat("順位", 3))        # 横に並べる
```

セルの途中で表示したい場合は `ui.show(...)` を使います。Google Colab ではその場に表示され、IPython のない PyHiroba ではコンポーネントを返すので、セル最後の式として置きます。

### 外部への通信について

コンポーネントを表示しても、外部との通信は発生しません。書体は PyHiroba と同じ Zen Kaku Gothic New を名前で指定しており、ファイルの取得は行いません。PyHiroba ではページ側が読み込み済みのため、これで見た目が揃います。書体を持っていない環境（Google Colab など）では、端末にある書体で表示されます。

Google Colab でも同じ書体に揃えたい場合は `ui.use_web_font(True)` を呼ぶことで、Google Fonts から読み込めます。この場合は表示のたびに Google へ通信が発生し、閲覧者の IP アドレスが渡ります。

`ai` がモデルを受け取るときを除けば、外部へ通信する箇所はありません。

### クイズの答えについて

`ui.quiz()` は JavaScript を使わず、CSS で正誤を表示しています。そのため、答えは出力の HTML に含まれます。ブラウザの「ソースを表示」や検証ツールを開くと読み取れるので、点数をつける試験ではなく、自分で確認するための練習に向いています。

## 入力を Python に戻す

`ui.form()` は入力欄とボタンを表示し、押されたときに関数を呼びます。入力欄の名前が、そのままキーワード引数になります。

```python
def ask(question, level):
    return ui.card(question, f"{level} 向けの答えです")

ui.form(ask,
        ui.field("question", label="質問", placeholder="スマホは持っていっていい？"),
        ui.field("level", label="学年", kind="choice", choices=["1年", "2年", "3年"]),
        title="校則について聞いてみよう", submit_label="聞く")
```

入力欄の種類は `text`（既定）/ `number` / `multiline` / `choice` です。`ui.field` の代わりに文字列を渡すと、その名前のテキスト欄になります。

動かし方は環境に合わせて自動で切り替わります。

| 環境 | 動作 |
|---|---|
| Google Colab・Jupyter（ipywidgets あり） | テキスト欄とボタンの対話 UI。押すたびに関数が呼ばれます |
| ipywidgets が無い環境 | `input()` で順に聞いて、結果を表示します |
| PyHiroba | HTML のフォームを表示し、入力された値を Python に返します |

先生が書くコードは1つで済み、環境ごとの切り替えは不要です。

### チャット形式にする

`ui.chat()` は会話を吹き出しで並べます。役割は `user` / `assistant` / `note` の3つで、`content` には文字列のほか他のコンポーネントも入れられます。

会話を変数にためて `ui.chat()` を返すようにすると、1つのセルでチャットができます。`clear_on_submit=True` を付けると、送信のたびに入力欄が空になります。

```python
history = []

def ask(question):
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": f"「{question}」ですね。"})
    return ui.chat(history, names={"user": "あなた", "assistant": "ボット"})

ui.form(ask, ui.field("question", label="質問"),
        submit_label="送信", clear_on_submit=True)
```

## AI（LLM）

`ai` は、LLM をその場で動かします。メソッドは4つです。

```python
from library_hiroba import ai

await ai.models()                  # 選べるモデルの一覧
await ai.load()                    # モデルを読み込む（初回は時間がかかります）
print(await ai.ask("日本の四季について、2行で書いて"))

async for chunk in ai.stream("俳句を1つ"):   # 書けたぶんから受け取る
    print(chunk, end="")
```

`ask()` には `max_tokens` を渡せます（既定は 256）。

```python
print(await ai.ask("俳句を1つ作って", max_tokens=64))
```

### 動作環境

| 環境 | 動かし方 | 用意するもの |
|---|---|---|
| PyHiroba | ブラウザの中で動きます（本体が用意した経路を使います） | なし |
| Google Colab・Jupyter | `transformers` と `torch` で動きます | `!pip install "library-hiroba[ai]"` |

### 選べるモデル

`load()` に名前を渡すとモデルを選べます。

```python
await ai.load("llmjp150m")
```

軽いものから順に並べています。校内の回線では、右の数字を先に見てください。

| 名前 | 内容 | 目安の通信量（ブラウザ／Google Colab） |
|---|---|---|
| `llmjp150m` | LLM-jp-3 150M。国産でとても軽い一方、文章は不自然です | 約 255MB ／ 約 600MB |
| `qwen3_06` | Qwen3 0.6B。`qwen05` より新しく、日本語が少し良いです | 約 550MB ／ 約 1.5GB |
| `qwen05`（既定） | Qwen2.5 0.5B。日本語が使えます | 約 900MB ／ 約 1.0GB |
| `qwen3_17` | Qwen3 1.7B。この中でいちばん賢い一方、いちばん重いです | 約 1.3GB ／ 約 3.4GB |
| `qwen15` | Qwen2.5 1.5B。日本語がより自然ですが重いです | 約 1.6GB ／ 約 3.1GB |

ブラウザ側は同じモデルを精度違いで並べるため `qwen05-q8` のように末尾が付いた名前も使えます。精度まで指定したいときはそちらを、そうでなければ上の共通の名前を使ってください。共通の名前はどちらの環境でも通ります。

### チャットとして表示する

`ui.form()`・`ui.chat()` と組み合わせると、1つのセルで対話ができます。

```python
history = []

async def ask(question):
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": await ai.ask(question)})
    return ui.chat(history, names={"user": "あなた", "assistant": "AI"})

await ai.load()
ui.form(ask, ui.field("question", label="質問"),
        submit_label="送信", clear_on_submit=True)
```

`handler` は `async def` で書けます。`ui.form()` は返り値が `await` の要るものかどうかを見て、必要なら待ってから表示します。送信のたびに会話全体を描き直すので、吹き出しが下に伸びていきます。入力欄は `clear_on_submit=True` で空に戻ります。

送信を押すと、答えが返るまで「考え中」の点が動きます。言葉を変えるときは `pending="AI が考えています"`、出さないときは `pending=None` を渡してください。

はじめに `await ai.load()` を済ませておくと、1通目でモデルの読み込み（数十秒〜）を待たされずに済みます。

### 書けたところから少しずつ出す

`ai.stream()` は、答えを書けたぶんから返します。`handler` を `yield` で書くと、届くたびに表示が差し替わります。

```python
history = []

async def talk(question):
    history.append({"role": "user", "content": question})
    text = ""
    async for chunk in ai.stream(question):
        text += chunk
        yield ui.chat(history + [{"role": "assistant", "content": text}],
                      names={"user": "あなた", "assistant": "AI"})
    history.append({"role": "assistant", "content": text})

await ai.load()
ui.form(talk, ui.field("question", label="質問"),
        submit_label="送信", clear_on_submit=True)
```

`ai.stream()` を全部つなげると `ai.ask()` と同じ文になります。少しずつ返せない環境では、書き終えてから一度にまとめて返すため、どちらでも同じコードが動きます。考えている途中（`<think>`）は、途中で切れても取り除かれます。

モデルのライセンスは配布元をご確認ください（既定の Qwen2.5 は Apache-2.0）。

## デザイン

配色・書体・形状は PyHiroba 本体のデザイントークンに合わせています。

| 項目 | 値 |
|---|---|
| ブランドカラー | `#028DAE`（ダーク時 `#35aecb`） |
| 書体 | Zen Kaku Gothic New を名前で指定しています。PyHiroba ではページ側が持っているため揃います。持っていない環境では `system-ui` になります |
| 角丸 | カード 14px、行とアラート 8px、バッジと進捗バー 999px |
| 記号 | 文字記号（`i` `✓` `!` `×`）を CSS の円形マークに載せて表します |

### テーマ

既定はライトです。ダークになるのは、祖先要素に `data-theme="dark"` が付いているとき、すなわち PyHiroba でダークモードに切り替えたときです。OS の配色設定は参照しません。これは PyHiroba 本体と同じ方針で、ページがライト表示のままコンポーネントが暗くなる食い違いを避けるためです。

背景を持つコンポーネントは不透明な色で塗ってあるので、ページの下地が何色でも文字と背景の組み合わせが保たれます。背景を持たない部分（進捗バーのラベルや表のキャプション）はページの文字色を受け継ぎ、暗いページでも読めます。

### テーマ変数

配色は CSS カスタムプロパティとして公開しています。`ui.html()` の `css` から使うと、テーマの切り替えに自動で追従します。

```python
ui.html('<div class="box">ヒント</div>',
        css=".box { border: 2px solid var(--hui-accent); background: var(--hui-accent-soft); }")
```

主な変数は次のとおりです。

| 用途 | 変数 |
|---|---|
| ブランド色 | `--hui-accent`（線・塗り）、`--hui-accent-ink`（文字）、`--hui-accent-soft`（背景） |
| 状態色 | `--hui-ok` / `--hui-warn` / `--hui-bad`（それぞれ `-ink` と `-soft` あり） |
| 文字 | `--hui-ink` / `--hui-ink-2` / `--hui-ink-3`、`--hui-on-accent`（アクセント色の上に載せる文字） |
| 面 | `--hui-paper` / `--hui-bg-2` / `--hui-line` |
| 形 | `--hui-radius` / `--hui-radius-sm` / `--hui-shadow` |

## 動作のしくみ

各コンポーネントは、必要な CSS を同梱した自己完結の HTML を返します。同じ CSS が何度出力されても表示は変わりません。渡したテキストはすべて HTML エスケープされ、改行は `<br>` になります。エスケープしない経路は `ui.html()` です。

コンポーネントの表示と CSS による操作は、どの環境でも同じように動きます。入力を Python に戻す `ui.form()` は環境によって経路が変わり、PyHiroba では本体が用意した経路を通ります。

`ai` も環境によって経路が変わります。PyHiroba では本体が用意した経路を通し、Google Colab では `transformers` を使います。書き方は同じですが、動くモデルの実体と読み込みにかかる時間は環境で違います。`ui` は純 Python のままで、`ai` を使わないかぎり追加の依存は読み込まれません。

## 開発

```bash
pip install -e ".[dev]"
ruff check src tests tools && pytest        # lint とテスト
python tools/build_gallery.py --shots       # 全コンポーネントのギャラリーとスクリーンショットを生成
python tools/check_ai_colab.py              # ai の Google Colab 経路を実際に動かす（[ai] が必要）
```

リリース手順は [`docs/RELEASING.md`](https://github.com/funakoshi-takehiro/library-hiroba/blob/main/docs/RELEASING.md) にあります。

## ライセンス

[MIT](https://github.com/funakoshi-takehiro/library-hiroba/blob/main/LICENSE)
