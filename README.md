# ui-hiroba

**Google Colab と PyHiroba の両方で動く、サーバー不要の教育向け UI 表示ライブラリ**

Gradio 風の書き心地で、HTML/CSS の UI 部品（カード・クイズ・進捗バーなど）をノートブックのセル出力に表示します。JavaScript もサーバーも使わないため、ブラウザ内完結の PyHiroba でもそのまま動きます。

```python
import ui_hiroba as ui

ui.card("今日の目標", "for文を使って、九九の表を作ってみよう！", icon="🎯")
```

> 🚧 現在 v1 を開発中です。
