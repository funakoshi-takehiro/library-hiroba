# ui-hiroba

Google Colab と PyHiroba で動く、教育向けの UI 表示ライブラリです。カード・クイズ・進捗バーといった部品を、ノートブックのセル出力にそのまま表示します。

[PyHiroba](https://pyhiroba.weblab.t.u-tokyo.ac.jp/) は、インストールも登録も必要とせず、ブラウザだけで Python を学べる、日本の学校現場向けの学習環境です。

```python
import ui_hiroba as ui

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

CSS はその部品の内側だけに適用されるため、クラス名を気軽に付けてもページの他の部分に影響しません。ふきだし・手順ステップ・単語カード・横棒グラフなどの作例は [`notebooks/html_css_recipes.ipynb`](notebooks/html_css_recipes.ipynb) にまとめてあります。

そのほかの特徴は次のとおりです。

| 項目 | 内容 |
|---|---|
| 動作環境 | セル最後の式を `_repr_html_()` で表示する共通のしくみに乗るため、Colab と PyHiroba で表示が一致します |
| 実装方式 | 表示も操作も HTML と CSS だけで完結します（クイズの正誤表示は `:checked`、開閉は `<details>`） |
| 依存関係 | 純 Python で依存ライブラリはありません。配布物は `py3-none-any` の wheel で、Colab の pip でも Pyodide の micropip でも取得できます |
| 見た目 | 配色・書体・角丸を PyHiroba 本体のデザインに合わせています |
| 配慮 | 配色は WCAG 4.5:1 以上を確認済みで、アニメーションは `prefers-reduced-motion` に従います |

## インストール

Google Colab と Jupyter:

```
%pip install ui-hiroba
```

PyHiroba では、同梱されていれば `import ui_hiroba` だけで使えます。同梱前の環境では `!pip install ui-hiroba` を実行すると micropip が PyPI から取得します。

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
| PyHiroba | HTML のフォームを表示します。値を受け取るには本体側の対応が必要です（[`docs/PYHIROBA_FORMS.md`](docs/PYHIROBA_FORMS.md) に設計案があります） |

先生が書くコードは1つで済み、環境ごとの切り替えは不要です。

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

書体は Google Fonts から読み込みます。オフラインや閉域網では `system-ui` に切り替わるだけで、表示は保たれます。外部との通信を完全になくす場合は、`src/ui_hiroba/_css.py` の `FONT_IMPORT` を空文字にします。

## しくみと範囲

各部品は、必要な CSS を同梱した自己完結の HTML を返します。同じ CSS が何度出力されても表示は変わりません。渡したテキストはすべて HTML エスケープされ、改行は `<br>` になります。エスケープしない経路は `ui.html()` だけです。

現在の版が扱うのは表示と CSS による操作です。入力値を Python に戻すしくみは含みません。またクイズの正解は HTML の class として含まれるため、成績評価ではなく学習用の自己チェックに向いています。

## 開発

```bash
pip install -e ".[dev]"
ruff check src tests tools && pytest        # lint とテスト
python tools/build_gallery.py --shots       # 全部品のギャラリーとスクリーンショットを生成
```

| ノートブック | 内容 |
|---|---|
| [`notebooks/demo_colab.ipynb`](notebooks/demo_colab.ipynb) | 全部品の動作確認 |
| [`notebooks/html_css_recipes.ipynb`](notebooks/html_css_recipes.ipynb) | HTML/CSS の作例集 |
| [`notebooks/demo_pyhiroba.md`](notebooks/demo_pyhiroba.md) | PyHiroba に貼り付けるセル一覧 |
| [`examples/school_rules_bot.ipynb`](examples/school_rules_bot.ipynb) | 校則チャットボットの教材（Google Colab 専用） |

`.ipynb` は PyHiroba の「ファイルを開く」からも読み込めます。テストは `notebooks/` の各ノートブックのコードセルを実際に実行し、出力が安全チェックを通ることまで確認します。

`examples/` は ui-hiroba を使った教材の作例です。PyTorch など重いライブラリを使うため Google Colab で動かします。テストの対象には含めません。

リリース手順は [`docs/RELEASING.md`](docs/RELEASING.md) を参照してください。

## ライセンス

[MIT](LICENSE)
