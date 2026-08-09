# library-hiroba

Google Colab と PyHiroba で、同じコードが同じように動く教育向けのライブラリです。入口は2つあります。

| 入口 | できること |
|---|---|
| `ui` | カード・クイズ・進捗バーといった部品を、ノートブックのセル出力にそのまま表示します |
| `ai` | 小さな言語モデルを、その場（ブラウザまたはノートブック）で動かします |

[PyHiroba](https://pyhiroba.weblab.t.u-tokyo.ac.jp/) は、インストールも登録も必要とせず、ブラウザだけで Python を学べる、日本の学校現場向けの学習環境です。

```python
from library_hiroba import ai, ui

ui.card("今日の目標", "for文を使って、九九の表を作ってみよう！")
```

```python
ui.quiz("2の8乗はいくつ？", choices=[128, 256, 512], answer=256,
        explanation="2を8回かけると 256 になるよ。")
# 選択肢を選ぶと色とマークで正誤が表示され、「解説を見る」で解説が開きます
```

## 特徴

用意された部品に加えて、HTML と CSS を自由に書けます。教材に必要な見た目は、たいていこの2つで作れます。

```python
ui.html('<div class="fukidashi">まずは print() を試してみよう</div>',
        css=".fukidashi { border: 2px solid var(--hui-accent); border-radius: 14px; padding: 10px 16px; }")
```

CSS はその部品の内側だけに適用されるため、クラス名を気軽に付けてもページの他の部分に影響しません。ふきだし、手順ステップ、単語カード、横棒グラフといった見た目も、この方法で作れます。

そのほかの特徴は次のとおりです。

| 項目 | 内容 |
|---|---|
| 動作環境 | セル最後の式を `_repr_html_()` で表示する共通のしくみに乗るため、Colab と PyHiroba で表示が一致します |
| 実装方式 | 表示も操作も HTML と CSS だけで完結します（クイズの正誤表示は `:checked`、開閉は `<details>`） |
| 依存関係 | `ui` は純 Python で依存ライブラリがありません。配布物は `py3-none-any` の wheel で、Colab の pip でも Pyodide の micropip でも取得できます（`ai` を Colab で使うときだけ追加の依存が要ります） |
| 見た目 | 配色・書体・角丸を PyHiroba 本体のデザインに合わせています |
| 配慮 | 配色は WCAG 4.5:1 以上を確認済みで、アニメーションは `prefers-reduced-motion` に従います |

## インストール

Google Colab と Jupyter:

```
%pip install library-hiroba
```

Colab で `ai` も使うときは、追加の依存（transformers と torch）を含めます。

```
%pip install "library-hiroba[ai]"
```

PyHiroba では、同梱されていれば `import library_hiroba` だけで使えます。`ai` の実行はブラウザ側の経路を使うので、追加のインストールは要りません。同梱前の環境では `!pip install library-hiroba` を実行すると micropip が PyPI から取得します。

## 部品一覧

| 部品 | 例 |
|---|---|
| 説明カード | `ui.card("今日の目標", "本文", footer="ヒント")` |
| ヒント・注意 | `ui.alert("メッセージ", kind="warning", title="よくあるまちがい")`（kind: `info` / `success` / `warning` / `danger`） |
| 選択式クイズ | `ui.quiz("問題", choices=[128, 256, 512], answer=256, explanation="解説")`（`answer` は値で指定します） |
| 答えの開閉 | `ui.reveal("答えは42", summary="答えを見る")` |
| 進捗バー | `ui.progress(7, max=10, label="練習問題")` |
| 数値タイル | `ui.stat("正答率", 85, unit="%")` |
| 横並び配置 | `ui.columns(部品1, 部品2, widths=[2, 1])` |
| バッジ | `ui.badge("重要", color="red")`（color: `blue` / `green` / `red` / `amber` / `gray`） |
| テーブル | `ui.table([{"名前": "佐藤", "得点": 90}], caption="結果")` |
| 自由 HTML/CSS | `ui.html('<div class="x">…</div>', css=".x { color: hotpink; }")` |
| 入力フォーム | `ui.form(handler, ui.field("question", label="質問"))` |
| 会話の表示 | `ui.chat([{"role": "user", "content": "…"}, {"role": "assistant", "content": "…"}])` |

複数の部品は次のようにまとめます。

```python
ui.stack(ui.card("目標", "..."), ui.progress(3, max=10))   # 縦に積む
ui.columns(ui.stat("得点", 90), ui.stat("順位", 3))        # 横に並べる
```

セルの途中で表示したい場合は `ui.show(...)` を使います。Colab ではその場に表示され、IPython のない PyHiroba では部品を返すので、セル最後の式として置きます。

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
| Colab・Jupyter（ipywidgets あり） | テキスト欄とボタンの対話 UI。押すたびに関数が呼ばれます |
| ipywidgets が無い環境 | `input()` で順に聞いて、結果を表示します |
| PyHiroba | HTML のフォームを表示します。値を受け取るには本体側の対応が必要です（[`docs/PYHIROBA_FORMS.md`](https://github.com/funakoshi-takehiro/library-hiroba/blob/main/docs/PYHIROBA_FORMS.md) に設計案があります） |

先生が書くコードは1つで済み、環境ごとの切り替えは不要です。

### チャット形式にする

`ui.chat()` は会話を吹き出しで並べます。役割は `user` / `assistant` / `note` の3つで、`content` には文字列のほか他の部品も入れられます。

会話を変数にためて `ui.chat()` を返すようにすると、1つのセルだけでチャットができます。`clear_on_submit=True` を付けると、送信のたびに入力欄が空になります。

```python
history = []

def ask(question):
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": f"「{question}」ですね。"})
    return ui.chat(history, names={"user": "あなた", "assistant": "ボット"})

ui.form(ask, ui.field("question", label="質問"),
        submit_label="送信", clear_on_submit=True)
```

## AI（小さな言語モデル）

`ai` は、小さな言語モデルをその場で動かします。メソッドは3つだけです。

```python
from library_hiroba import ai

await ai.models()                  # 選べるモデルの一覧
await ai.load()                    # モデルを読み込む（初回だけ時間がかかります）
print(await ai.ask("日本の四季について、2行で書いて"))
```

`await` が必要です。ノートブック（Colab / Jupyter / PyHiroba）では、セルの中にそのまま `await` を書けます。PyHiroba は GitHub Pages 配信のため `SharedArrayBuffer` を使った同期待ちができず、ブラウザ側は待つ形にせざるを得ません。Colab 側は待つ必要がありませんが、**同じコードが両方で動く**ことを優先して形を揃えています。

`ask()` には `max_tokens` を渡せます（既定は 256）。

```python
print(await ai.ask("俳句を1つ作って", max_tokens=64))
```

### 動く場所

| 環境 | 動かし方 | 用意するもの |
|---|---|---|
| PyHiroba | ブラウザの中で動きます（本体が用意した経路を使います） | なし |
| Colab・Jupyter | `transformers` と `torch` で動きます | `%pip install "library-hiroba[ai]"` |

どちらの経路でも、入力した文章が外部に送られることはありません。通信が起きるのはモデルを受け取るときだけです。

### 選べるモデル

`load()` に名前を渡すとモデルを選べます。

```python
await ai.load("llmjp150m")
```

| 名前 | 内容 | 目安の通信量（ブラウザ／Colab） |
|---|---|---|
| `qwen05`（既定） | Qwen2.5 0.5B。日本語が使えます | 約 900MB ／ 約 1.0GB |
| `qwen15` | Qwen2.5 1.5B。日本語がより自然ですが重いです | 約 1.6GB ／ 約 3.1GB |
| `llmjp150m` | LLM-jp-3 150M。国産でとても軽い一方、文章は不自然です | 約 255MB ／ 約 600MB |

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

`handler` は `async def` で書けます。`ui.form()` は返り値が `await` の要るものかどうかを見て、必要なら待ってから表示します。入力を Python に戻す経路は環境によって変わるため、この組み合わせが動くのは今のところ Colab・Jupyter です（PyHiroba は本体側の対応待ちです）。

モデルのライセンスは配布元をご確認ください（既定の Qwen2.5 は Apache-2.0）。

## デザイン

配色・書体・形状は PyHiroba 本体のデザイントークンに合わせています。

| 項目 | 値 |
|---|---|
| ブランドカラー | `#028DAE`（ダーク時 `#35aecb`） |
| 書体 | Zen Kaku Gothic New。読み込めない環境では `system-ui` に自動で切り替わります |
| 角丸 | カード 14px、行とアラート 8px、バッジと進捗バー 999px |
| 記号 | 文字記号（`i` `✓` `!` `×`）を CSS の円形マークに載せて表します |

### テーマ

既定はライトです。ダークになるのは、祖先要素に `data-theme="dark"` が付いているとき、すなわち PyHiroba でダークモードに切り替えたときだけです。OS の配色設定は参照しません。これは PyHiroba 本体と同じ方針で、ページがライト表示のまま部品だけが暗くなる食い違いを避けるためです。

背景を持つ部品は不透明な色で塗ってあるので、ページの下地が何色でも文字と背景の組み合わせが保たれます。背景を持たない部分（進捗バーのラベルや表のキャプション）はページの文字色を受け継ぎ、暗いページでも読めます。

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

書体は Google Fonts から読み込みます。オフラインや閉域網では `system-ui` に切り替わるだけで、表示は保たれます。外部との通信を完全になくす場合は、`src/library_hiroba/_css.py` の `FONT_IMPORT` を空文字にします。

## しくみと範囲

各部品は、必要な CSS を同梱した自己完結の HTML を返します。同じ CSS が何度出力されても表示は変わりません。渡したテキストはすべて HTML エスケープされ、改行は `<br>` になります。エスケープしない経路は `ui.html()` だけです。

部品の表示と CSS による操作は、どの環境でも同じように動きます。入力を Python に戻す `ui.form()` は環境によって経路が変わり、PyHiroba では本体側の対応を待っています。

`ai` も環境によって経路が変わります。PyHiroba では本体が用意した経路を通し、Colab では `transformers` を使います。書き方は同じですが、動くモデルの実体と読み込みにかかる時間は環境で違います。`ui` は純 Python のままで、`ai` を使わないかぎり追加の依存は読み込まれません。

クイズの正解は HTML の class として含まれるため、成績評価ではなく学習用の自己チェックに向いています。

## 開発

```bash
pip install -e ".[dev]"
ruff check src tests tools && pytest        # lint とテスト
python tools/build_gallery.py --shots       # 全部品のギャラリーとスクリーンショットを生成
python tools/check_ai_colab.py              # ai の Colab 経路を実際に動かす（[ai] が必要）
```

- リリース手順: [`docs/RELEASING.md`](https://github.com/funakoshi-takehiro/library-hiroba/blob/main/docs/RELEASING.md)
- PyHiroba に同梱するときの取り決め（ファイル一覧・`ai` の受け渡し）: [`docs/PYHIROBA_INTEGRATION.md`](https://github.com/funakoshi-takehiro/library-hiroba/blob/main/docs/PYHIROBA_INTEGRATION.md)

## ライセンス

[MIT](https://github.com/funakoshi-takehiro/library-hiroba/blob/main/LICENSE)
