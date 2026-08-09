# library-hiroba デモ（PyHiroba 用セル一覧）

[PyHiroba](https://pyhiroba.weblab.t.u-tokyo.ac.jp/) のノートブックに、以下のコードブロックを1つずつセルとして貼り付けて実行してください。部品はセル最後の式に置くと表示されます。

library-hiroba が同梱されていれば `import` だけで使えます。同梱前の環境では、最初に `!pip install library-hiroba` を実行してください。

## セル1: インポート

```python
from library_hiroba import ui

ui.card("library-hiroba へようこそ", "このカードが表示されたら準備OK！")
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

## セル4: 選択式クイズ

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

## セル9: 複数部品をまとめて表示

```python
# PyHiroba には IPython がないため、show() は部品を返します。
# セル最後の式として置くと、まとめて表示されます。
ui.show(
    ui.card("まとめ", "きょうは for文 を勉強したよ"),
    ui.progress(100, label="今日の目標"),
)
```

## セル10: 自由な HTML + CSS

```python
# HTML はそのまま表示されます。css は既定でこの部品の内側だけに適用されます
# （scoped=False を指定するとページ全体に適用されます）
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

## セル11: AI（本体が対応している環境のみ）

`ai` はブラウザの中で小さな言語モデルを動かします。PyHiroba 本体の受け渡し経路（`js.pyhirobaAsk`）が用意されている環境でだけ動きます。

```python
from library_hiroba import ai

await ai.models()
```

```python
# 初回はモデルの取得に時間がかかります（llmjp150m で 255MB 前後）
print(await ai.load("llmjp150m"))
print(await ai.ask("日本の四季について、2行で書いて"))
```

Colab でも同じコードが動きます（そちらは `transformers` を使います）。

## 確認ポイント

- すべての部品が表示される
- クイズで選択肢を選ぶと、正解は緑、まちがいは赤で表示される
- 「答えを見る」「解説を見る」がクリックで開閉する
- ダークモードに切り替えると配色が追従する（既定はライトで、OS の配色設定は参照しません）
- 同じ部品を複数のセルに出しても表示が保たれる
