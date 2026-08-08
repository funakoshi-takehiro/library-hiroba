# ui-hiroba

**Google Colab と PyHiroba の両方で動く、サーバー不要の教育向け UI 表示ライブラリ**

Gradio 風の書き心地で、HTML/CSS の UI 部品（カード・クイズ・進捗バーなど）をノートブックのセル出力に表示します。JavaScript もサーバーも使わないため、ブラウザ内完結の PyHiroba でもそのまま動き、公開・運用コストは0円です。

```python
import ui_hiroba as ui

ui.card("今日の目標", "for文を使って、九九の表を作ってみよう！")
```

```python
ui.quiz("2の8乗はいくつ？", choices=[128, 256, 512], answer=256,
        explanation="2を8回かけると 256 になるよ。")
# → 選ぶと色とマークで正誤がわかり、「解説を見る」で開閉できる
```

## 特徴

- **PyHiroba と同じ見た目** — ブランドカラー・書体（Zen Kaku Gothic New）・角丸・シャドウを PyHiroba 本体のデザイントークンに合わせている。絵文字は使わない
- **両環境で同じ表示** — セル最後の式の `_repr_html_()` を表示する共通規約に乗るだけ。Colab のサンドボックス iframe でも、PyHiroba のサニタイザ（DOMPurify）を通しても、出力は一切変化しない
- **JavaScript 完全不使用** — インタラクション（クイズの正誤表示・開閉）は CSS のみ（`:checked`・`<details>`）
- **依存ゼロ・純 Python** — wheel は `py3-none-any`。Colab の pip でも Pyodide の micropip でも入る
- **ダークモード両対応** — OS の `prefers-color-scheme` と PyHiroba の `data-theme` 切替の両方に追従（配色は両テーマで WCAG 4.5:1 以上を検証済み）
- **ホストを汚さない** — CSS は `hui-` 接頭辞で名前空間化。`id` 属性は不使用、radio の `name` はセルごとに一意（全セルが 1 document を共有する PyHiroba でも衝突しない）
- **アニメーションは `prefers-reduced-motion` を尊重**

## インストール

**Google Colab / Jupyter:**

```
%pip install ui-hiroba
```

**PyHiroba:** 同梱（vendor）されていれば `import ui_hiroba` だけで使えます。同梱前の環境では `!pip install ui-hiroba`（micropip が PyPI から取得）。

## 部品一覧（v1）

| 部品 | 例 |
|---|---|
| 説明カード | `ui.card("今日の目標", "本文", footer="ヒント")` |
| ヒント・注意 | `ui.alert("メッセージ", kind="warning", title="よくあるまちがい")` — kind: `info` / `success` / `warning` / `danger` |
| 選択式クイズ | `ui.quiz("問題", choices=[128, 256, 512], answer=256, explanation="解説")` — `answer` は**値**で指定 |
| 答えの開閉 | `ui.reveal("答えは42", summary="答えを見る")` |
| 進捗バー | `ui.progress(7, max=10, label="練習問題")` |
| 数値タイル | `ui.stat("正答率", 85, unit="%")` |
| 横並び配置 | `ui.columns(部品1, 部品2, widths=[2, 1])` |
| バッジ | `ui.badge("重要", color="red")` — color: `blue` / `green` / `red` / `amber` / `gray` |
| テーブル | `ui.table([{"名前": "佐藤", "得点": 90}], caption="結果")` |
| 自由 HTML/CSS | `ui.html('<div class="x">…</div>', css=".x { color: hotpink; }")` — HTML はエスケープされない明示的な逃げ道。`css` で自由な CSS も同梱でき、既定でこの部品の範囲だけに自動スコープされる（`scoped=False` でスコープ解除） |

複数の部品をまとめるには:

```python
ui.stack(ui.card("目標", "..."), ui.progress(3, max=10))   # 縦に積む
ui.columns(ui.stat("得点", 90), ui.stat("順位", 3))        # 横に並べる
```

セルの**途中**で表示したいとき（ループ内など）は `ui.show(...)`。Colab ではその場に表示され、IPython のない PyHiroba では部品を返すのでセル最後の式として置きます。

## デザイン（PyHiroba との統一）

配色・書体・形状は PyHiroba 本体（`css/style.css`）のデザイントークンに合わせています。

| 項目 | 値 |
|---|---|
| ブランドカラー | `#028DAE`（ダーク時 `#35aecb`） |
| 書体 | Zen Kaku Gothic New（`font-feature-settings: "palt"`）。読み込めない環境では `system-ui` に自動フォールバック |
| 角丸 | カード 14px / 行・アラート 8px / バッジ・進捗バー 999px |
| 記号 | 絵文字は使わず、文字記号（`i` `✓` `!` `×`）を CSS の円形マークに載せる |

これらは CSS カスタムプロパティとして公開しているので、`ui.html()` の `css` からも使えます。テーマ切替に自動で追従します:

```python
ui.html('<div class="box">ヒント</div>',
        css=".box { border: 2px solid var(--hui-accent); background: var(--hui-accent-soft); }")
```

主な変数: `--hui-accent` / `--hui-accent-ink`（テキスト用の濃い版）/ `--hui-accent-soft`（背景用）、`--hui-ok` / `--hui-warn` / `--hui-bad`（同じく `-ink` `-soft` あり）、`--hui-on-accent`（アクセント色で塗った上に載せる文字色）、`--hui-ink` / `--hui-ink-2` / `--hui-ink-3`、`--hui-paper` / `--hui-bg-2` / `--hui-line`、`--hui-radius` / `--hui-radius-sm` / `--hui-shadow`。

作例は [`notebooks/html_css_recipes.ipynb`](notebooks/html_css_recipes.ipynb) にまとめてあります。

**フォントの読み込みについて**: 部品の CSS には Google Fonts の `@import` が含まれます（PyHiroba 本体と同じ書体を Colab でも表示するため）。オフラインや閉域網では取得に失敗しても `system-ui` にフォールバックするだけで、表示は崩れません。外部通信を完全にゼロにしたい場合は `src/ui_hiroba/_css.py` の `FONT_IMPORT` を空文字にしてください。

## 仕組みと制約（v1）

- 各部品は必要な CSS を同梱した自己完結 HTML を返します。同じ部品を何度出力しても CSS は冪等（重複無害）です
- ユーザーが渡したテキストはすべて HTML エスケープされます（`ui.html()` を除く）。改行は `<br>` になります
- v1 は**表示 + CSS インタラクション**が範囲です。「入力値を Python に戻す」「ボタンで Python 関数を実行する」（本家 Gradio 相当）は範囲外です
- クイズの正解情報は HTML 内に（class として）含まれます。ページのソースを見れば分かるため、成績評価ではなく学習用の自己チェックに使ってください

## 開発

```bash
pip install -e ".[dev]"
ruff check src tests tools && pytest        # lint + テスト（サニタイズ生存の不変条件を含む）
python tools/build_gallery.py               # 全部品のギャラリー HTML を tools/out/ に生成
python tools/build_gallery.py --shots       # + Playwright でライト/ダークのスクリーンショット
```

ノートブック:

| ファイル | 内容 |
|---|---|
| [`notebooks/demo_colab.ipynb`](notebooks/demo_colab.ipynb) | 全部品の動作確認（Colab / PyHiroba のどちらでも開けます） |
| [`notebooks/html_css_recipes.ipynb`](notebooks/html_css_recipes.ipynb) | **HTML/CSS レシピ集** — ふきだし・手順ステップ・単語カード・横棒グラフ・付箋・よい例わるい例など、コピーして使える作例 |
| [`notebooks/demo_pyhiroba.md`](notebooks/demo_pyhiroba.md) | PyHiroba に貼り付けるセル一覧（Markdown 版） |

`.ipynb` は PyHiroba の「ファイルを開く」からも読み込めます。テストは各ノートブックのコードセルを実際に実行し、出力が安全チェックを通ることまで検証しています。

リリース手順（PyPI Trusted Publishing）: [`docs/RELEASING.md`](docs/RELEASING.md)

## ライセンス

[MIT](LICENSE)
