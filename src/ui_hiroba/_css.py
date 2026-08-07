"""ui_hiroba の CSS 定義。

設計上の不変条件:

- すべてのセレクタは ``hui-`` 接頭辞（ルートは ``.hui``）で名前空間化する。
  PyHiroba では全セルの出力が 1 つの document を共有するため、ホストページの
  スタイルを汚さない・汚されにくいことが必須。
- 内容は完全に静的な文字列。同じ ``<style>`` ブロックがセルごとに重複挿入
  されても表示が変わらない（冪等）。
- JavaScript・イベント属性は一切使わない。インタラクションは CSS のみ
  （``:checked``・``<details>``）。``:has()`` はコア機能では使わず、
  ``@supports`` ガード付きの装飾強化に限る。
- 文字色は原則 ``inherit``。半透明ニュートラルとステータス4色（両テーマの
  下地で WCAG 4.5:1 以上を検証済み）だけをトークンとして持つ。
"""

# ライト/ダークのトークンは同じ変数名で値だけ差し替える。
# 状態色は必ずアイコンやラベルと併記して使う（色だけに意味を持たせない）。
_LIGHT_TOKENS = """\
  color-scheme: light;
  --hui-accent: #256abf;
  --hui-ok: #006300;
  --hui-warn: #9a6700;
  --hui-bad: #d03b3b;
  --hui-accent-bg: rgba(37, 106, 191, 0.09);
  --hui-ok-bg: rgba(0, 99, 0, 0.08);
  --hui-warn-bg: rgba(154, 103, 0, 0.10);
  --hui-bad-bg: rgba(208, 59, 59, 0.08);"""

_DARK_TOKENS = """\
  color-scheme: dark;
  --hui-accent: #5598e7;
  --hui-ok: #3fb950;
  --hui-warn: #e3b341;
  --hui-bad: #f47067;
  --hui-accent-bg: rgba(85, 152, 231, 0.16);
  --hui-ok-bg: rgba(63, 185, 80, 0.15);
  --hui-warn-bg: rgba(227, 179, 65, 0.13);
  --hui-bad-bg: rgba(244, 112, 103, 0.15);"""

# テーマの重ね順（後勝ち + 詳細度）:
#   1. .hui                      … ライト基準
#   2. @media dark の .hui       … OS がダーク（Colab iframe はこれしか手がかりがない）
#   3. [data-theme="dark"] .hui  … PyHiroba の手動ダーク（祖先のどの要素に付いていても効く）
#   4. [data-theme="light"] .hui … 明示ライトが 2 に勝つための再宣言
BASE_CSS = f"""\
.hui, .hui *, .hui *::before, .hui *::after {{ box-sizing: border-box; }}
.hui {{
  font-family: inherit;
  font-size: inherit;
  line-height: 1.6;
  color: inherit;
  --hui-border: rgba(127, 127, 127, 0.35);
  --hui-bg-soft: rgba(127, 127, 127, 0.10);
  --hui-bg-softer: rgba(127, 127, 127, 0.06);
  --hui-radius: 10px;
{_LIGHT_TOKENS}
}}
@media (prefers-color-scheme: dark) {{
  .hui {{
{_DARK_TOKENS}
  }}
}}
[data-theme="dark"] .hui {{
{_DARK_TOKENS}
}}
[data-theme="light"] .hui {{
{_LIGHT_TOKENS}
}}
.hui a {{ color: var(--hui-accent); }}"""

# コンポーネント別 CSS。辞書の定義順が <style> 内での出力順になる。
COMPONENT_CSS = {
    "text": """\
.hui-text { margin: 0.4em 0; }""",
    "card": """\
.hui-card {
  border: 1px solid var(--hui-border);
  border-radius: var(--hui-radius);
  background: var(--hui-bg-softer);
  padding: 14px 16px;
  margin: 8px 0;
}
.hui-card-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-weight: 600;
  font-size: 1.05em;
  margin: 0 0 6px;
}
.hui-card-icon { flex: none; }
.hui-card-footer {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--hui-border);
  font-size: 0.9em;
  opacity: 0.72;
}""",
    "alert": """\
.hui-alert {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border-left: 4px solid var(--hui-accent);
  background: var(--hui-accent-bg);
  border-radius: 8px;
  padding: 10px 14px;
  margin: 8px 0;
}
.hui-alert-icon { flex: none; }
.hui-alert-title { font-weight: 600; margin-bottom: 2px; }
.hui-alert-success { border-left-color: var(--hui-ok); background: var(--hui-ok-bg); }
.hui-alert-warning { border-left-color: var(--hui-warn); background: var(--hui-warn-bg); }
.hui-alert-danger { border-left-color: var(--hui-bad); background: var(--hui-bad-bg); }""",
    "quiz": """\
.hui-quiz {
  border: 1px solid var(--hui-border);
  border-radius: var(--hui-radius);
  padding: 14px 16px;
  margin: 8px 0;
}
.hui-quiz-q { font-weight: 600; margin: 0 0 10px; }
.hui-choice {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--hui-border);
  border-radius: 8px;
  padding: 8px 12px;
  margin: 6px 0;
  cursor: pointer;
}
@media (hover: hover) {
  .hui-choice:hover { border-color: var(--hui-accent); }
}
.hui-choice input[type="radio"] {
  flex: none;
  margin: 0;
  cursor: pointer;
  accent-color: var(--hui-accent);
}
.hui-fb {
  display: none;
  margin-left: auto;
  flex: none;
  font-weight: 700;
  font-size: 0.95em;
  white-space: nowrap;
}
.hui-choice input:checked ~ .hui-fb { display: inline; }
.hui-is-answer .hui-fb { color: var(--hui-ok); }
.hui-choice:not(.hui-is-answer) .hui-fb { color: var(--hui-bad); }
.hui-choice input:checked + .hui-choice-text { font-weight: 600; }
.hui-is-answer input:checked + .hui-choice-text { color: var(--hui-ok); }
.hui-choice:not(.hui-is-answer) input:checked + .hui-choice-text { color: var(--hui-bad); }
@supports selector(:has(*)) {
  .hui-is-answer:has(input:checked) {
    border-color: var(--hui-ok);
    background: var(--hui-ok-bg);
  }
  .hui-choice:not(.hui-is-answer):has(input:checked) {
    border-color: var(--hui-bad);
    background: var(--hui-bad-bg);
  }
}
.hui-quiz-exp { margin-top: 10px; }""",
    "reveal": """\
.hui-reveal {
  border: 1px solid var(--hui-border);
  border-radius: var(--hui-radius);
  background: var(--hui-bg-softer);
  margin: 8px 0;
  overflow: hidden;
}
.hui-reveal > summary {
  cursor: pointer;
  padding: 10px 14px;
  font-weight: 600;
  -webkit-user-select: none;
  user-select: none;
}
@media (hover: hover) {
  .hui-reveal > summary:hover { background: var(--hui-bg-soft); }
}
.hui-reveal[open] > summary { border-bottom: 1px solid var(--hui-border); }
.hui-reveal-body { padding: 12px 14px; }""",
    "progress": """\
.hui-progress { margin: 10px 0; }
.hui-progress-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.92em;
  margin-bottom: 4px;
}
.hui-progress-num { font-weight: 600; }
.hui-progress-track {
  height: 12px;
  border-radius: 999px;
  background: var(--hui-bg-soft);
  border: 1px solid var(--hui-border);
  overflow: hidden;
}
.hui-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--hui-accent);
}
@media (prefers-reduced-motion: no-preference) {
  .hui-progress-fill { transition: width 0.4s ease; }
}""",
    "stat": """\
.hui-stat {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  border: 1px solid var(--hui-border);
  border-radius: var(--hui-radius);
  background: var(--hui-bg-softer);
  padding: 12px 18px;
  margin: 8px 8px 0 0;
  min-width: 8em;
  vertical-align: top;
}
.hui-stat-label { font-size: 0.85em; opacity: 0.72; }
.hui-stat-value { font-size: 1.9em; font-weight: 700; line-height: 1.25; }
.hui-stat-unit { font-size: 0.55em; font-weight: 600; opacity: 0.72; margin-left: 2px; }""",
    "columns": """\
.hui-cols {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  margin: 8px 0;
}
.hui-col { flex: 1 1 0; min-width: 200px; }
.hui-col > :first-child { margin-top: 0; }
.hui-col > :last-child { margin-bottom: 0; }
.hui-col > .hui-stat { width: 100%; }""",
    "badge": """\
.hui-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid var(--hui-border);
  background: var(--hui-bg-soft);
  font-size: 0.85em;
  font-weight: 600;
  line-height: 1.6;
  margin: 0 4px 4px 0;
}
.hui-badge-blue { color: var(--hui-accent); background: var(--hui-accent-bg); }
.hui-badge-green { color: var(--hui-ok); background: var(--hui-ok-bg); }
.hui-badge-red { color: var(--hui-bad); background: var(--hui-bad-bg); }
.hui-badge-amber { color: var(--hui-warn); background: var(--hui-warn-bg); }""",
    "table": """\
.hui-table-wrap { overflow-x: auto; margin: 8px 0; }
.hui-table { border-collapse: collapse; min-width: 50%; }
.hui-table caption {
  caption-side: top;
  text-align: left;
  font-weight: 600;
  padding: 0 0 6px;
}
.hui-table th, .hui-table td {
  border: 1px solid var(--hui-border);
  padding: 6px 12px;
  text-align: left;
  font-size: 0.95em;
}
.hui-table thead th { background: var(--hui-bg-soft); }
.hui-table tbody tr:nth-child(even) { background: var(--hui-bg-softer); }""",
    "stack": """\
.hui-stack { display: flex; flex-direction: column; margin: 8px 0; }
.hui-stack > * { margin: 0; }
.hui-stack > .hui-badge, .hui-stack > .hui-stat { align-self: flex-start; }""",
}
