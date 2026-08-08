# ui-hiroba デモ（PyHiroba 用セル一覧）

PyHiroba のノートブックに、以下のコードブロックを1つずつセルとして貼り付けて実行してください。
部品は**セル最後の式**に置くと表示されます（PyHiroba は最後の式の `_repr_html_()` を拾って表示するため）。

> **前提**: ui-hiroba が PyHiroba に同梱（vendor）されていれば `import` だけで使えます。
> 同梱前の環境では、最初に `!pip install ui-hiroba` を実行してください（PyPI 公開後、
> micropip が pure Python wheel を取得します）。

## セル1: インポート

```python
import ui_hiroba as ui

ui.card("ui-hiroba へようこそ", "このカードが表示されたら準備OK！")
```

## セル2: 説明カード

```python
ui.card("今日の目標", "for文を使って、九九の表を作ってみよう！",
        footer="ヒント: range(1, 10) を2回使うよ")
```

## セル3: ヒント・注意

```python
ui.alert("range(5) は 0〜4 まで。5 は入らないよ", kind="warning", title="よくあるまちがい")
```

## セル4: 選択式クイズ（CSS だけで正誤表示）

```python
ui.quiz("2の8乗はいくつ？", choices=[128, 256, 512], answer=256,
        explanation="2を8回かけると 256 になるよ。Python では 2**8 で計算できる。")
```

## セル5: 答えの開閉

```python
ui.reveal("print('こんにちは') と書きます", summary="答えを見る")
```

## セル6: 進捗バー

```python
ui.progress(7, max=10, label="練習問題の進み具合")
```

## セル7: 数値タイル + 横並び

```python
ui.columns(
    ui.stat("正答率", 85, unit="%"),
    ui.stat("れんぞく正解", 4, unit="問"),
    ui.stat("学習時間", 25, unit="分"),
)
```

## セル8: テーブルとバッジ（縦積み）

```python
ui.stack(
    ui.badge("今週のポイント", color="green"),
    ui.table([
        {"名前": "佐藤", "得点": 90, "コメント": "よくできました"},
        {"名前": "鈴木", "得点": 85, "コメント": "おしい！"},
    ], caption="漢字テストの結果"),
)
```

## セル9: 複数部品をまとめて（show のフォールバック）

```python
# PyHiroba には IPython がないため、show() は部品を「返す」。
# セル最後の式として置けば、まとめて表示される。
ui.show(
    ui.card("まとめ", "きょうは for文 を勉強したよ"),
    ui.progress(100, label="今日の目標"),
)
```

## セル10: 自由な HTML + CSS

```python
# HTML はエスケープされない逃げ道。css は既定で「この部品の中」だけに効く
# （scoped=False にするとページ全体に効くので注意）
ui.html("""
<div class="fukidashi">こんにちは！<br>いっしょに <b>Python</b> を勉強しよう</div>
""", css="""
.fukidashi {
  display: inline-block;
  border: 2px solid var(--hui-accent);
  border-radius: 14px;
  padding: 10px 16px;
  background: var(--hui-accent-soft);
  font-weight: 700;
}
b { color: var(--hui-accent-ink); }
""")
```

## 確認ポイント

- すべての部品が表示される（サニタイザに何も削られない）
- クイズで選択肢を選ぶと、正解は緑・まちがいは赤で表示される
- 「答えを見る」「解説を見る」がクリックで開閉する
- PyHiroba のダークモードに切り替えると（`data-theme` 切替）配色が追従して読める
  （既定は必ずライト。OS の配色設定にはつられません）
- 同じ部品を複数セルに出しても壊れない（radio の name はセルごとに一意）
