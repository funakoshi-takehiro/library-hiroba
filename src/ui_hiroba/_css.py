"""ui_hiroba の CSS 定義。

デザインは PyHiroba 本体（css/style.css の V3 デザイン）に合わせている:
ティールのブランドカラー、Zen Kaku Gothic New、角丸14px、ソフトシャドウ、
絵文字を使わない記号表現。

設計上の不変条件:

- すべてのセレクタは ``hui-`` 接頭辞（ルートは ``.hui``）で名前空間化する。
  PyHiroba では全セルの出力が 1 つの document を共有するため、ホストページの
  スタイルを汚さない・汚されにくいことが必須。
- 内容は完全に静的な文字列。同じ ``<style>`` ブロックがセルごとに重複挿入
  されても表示が変わらない（冪等）。
- JavaScript・イベント属性は一切使わない。インタラクションは CSS のみ
  （``:checked``・``<details>``）。``:has()`` はコア機能では使わず、
  ``@supports`` ガード付きの装飾強化に限る。
- PyHiroba は出力を ``.output-html`` の中に入れるため、そこで定義済みの
  スタイル（テーブルの等幅フォント・右揃えなど）に負けないよう、競合する
  セレクタは ``.hui`` を前置して詳細度を上げる。
"""

# PyHiroba 本体と同じ書体。読み込めない環境（オフライン・閉域網）では
# 自動的に system-ui にフォールバックするため、表示は崩れない。
FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap');"
)

# トークンは PyHiroba の :root / :root[data-theme="dark"] に対応する。
# -ink 系はテキスト用に濃度を上げた派生色（ライトのサーフェス #ffffff / #fafaf8 と
# ダークのサーフェス #191e24 / #151a20 の双方で WCAG 4.5:1 以上を確認済み）。
_LIGHT_TOKENS = """\
  color-scheme: light;
  --hui-ink: #101418;
  --hui-ink-2: #2b3138;
  --hui-ink-3: #5b636c;
  --hui-paper: #ffffff;
  --hui-bg-2: #f3f1ec;
  --hui-line: #e7e5e0;
  --hui-accent: #028DAE;
  --hui-accent-ink: #017a97;
  --hui-accent-soft: rgba(2, 141, 174, 0.10);
  --hui-ok: #27ae60;
  --hui-ok-ink: #187f45;
  --hui-ok-soft: rgba(39, 174, 96, 0.10);
  --hui-warn: #f59e0b;
  --hui-warn-ink: #96610b;
  --hui-warn-soft: rgba(245, 158, 11, 0.12);
  --hui-bad: #e74c3c;
  --hui-bad-ink: #c0392b;
  --hui-bad-soft: rgba(231, 76, 60, 0.10);
  --hui-on-accent: #ffffff;
  --hui-shadow: 0 1px 0 rgba(16, 20, 24, 0.04), 0 4px 12px -6px rgba(16, 20, 24, 0.08);"""

_DARK_TOKENS = """\
  color-scheme: dark;
  --hui-ink: #e8eaed;
  --hui-ink-2: #c9cfd6;
  --hui-ink-3: #9aa3ad;
  --hui-paper: #191e24;
  --hui-bg-2: #21272e;
  --hui-line: #2c333b;
  --hui-accent: #35aecb;
  --hui-accent-ink: #35aecb;
  --hui-accent-soft: rgba(53, 174, 203, 0.16);
  --hui-ok: #4cc272;
  --hui-ok-ink: #58c97a;
  --hui-ok-soft: rgba(76, 194, 114, 0.14);
  --hui-warn: #f5b04b;
  --hui-warn-ink: #f5b04b;
  --hui-warn-soft: rgba(245, 176, 75, 0.14);
  --hui-bad: #f0705f;
  --hui-bad-ink: #f0705f;
  --hui-bad-soft: rgba(240, 112, 95, 0.14);
  --hui-on-accent: #0e1418;
  --hui-shadow: 0 1px 0 rgba(0, 0, 0, 0.35), 0 4px 12px -6px rgba(0, 0, 0, 0.45);"""

# テーマの重ね順（後勝ち + 詳細度）:
#   1. .hui                      … ライト基準
#   2. @media dark の .hui       … OS がダーク（Colab iframe はこれしか手がかりがない）
#   3. [data-theme="dark"] .hui  … PyHiroba の手動ダーク（<html> に付く）
#   4. [data-theme="light"] .hui … 明示ライトが 2 に勝つための再宣言
BASE_CSS = f"""\
{FONT_IMPORT}
.hui, .hui *, .hui *::before, .hui *::after {{ box-sizing: border-box; }}
.hui {{
  font-family: 'Zen Kaku Gothic New', system-ui, sans-serif;
  font-feature-settings: "palt";
  -webkit-font-smoothing: antialiased;
  font-size: 15px;
  line-height: 1.7;
  color: inherit;
  --hui-radius: 14px;
  --hui-radius-sm: 8px;
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
.hui a {{ color: var(--hui-accent-ink); }}
.hui b, .hui strong {{ font-weight: 700; }}"""

# コンポーネント別 CSS。辞書の定義順が <style> 内での出力順になる。
COMPONENT_CSS = {
    "text": """\
.hui-text { margin: 0.4em 0; }""",
    "card": """\
.hui-card {
  border: 1px solid var(--hui-line);
  border-radius: var(--hui-radius);
  background: var(--hui-paper);
  box-shadow: var(--hui-shadow);
  color: var(--hui-ink);
  padding: 16px 18px;
  margin: 10px 0;
}
.hui-card-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-weight: 700;
  font-size: 1.06em;
  letter-spacing: 0.01em;
  margin: 0 0 6px;
}
.hui-card-icon { flex: none; }
.hui-card-body { color: var(--hui-ink-2); }
.hui-card-footer {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--hui-line);
  font-size: 0.9em;
  color: var(--hui-ink-3);
}""",
    "alert": """\
.hui-alert {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border-radius: var(--hui-radius);
  background: var(--hui-accent-soft);
  color: var(--hui-ink);
  padding: 12px 16px;
  margin: 10px 0;
}
.hui-alert-icon {
  flex: none;
  width: 20px;
  height: 20px;
  margin-top: 3px;
  border-radius: 999px;
  background: var(--hui-accent);
  color: var(--hui-on-accent);
  font-size: 13px;
  font-weight: 900;
  line-height: 20px;
  text-align: center;
}
.hui-alert-title { font-weight: 700; letter-spacing: 0.01em; margin-bottom: 2px; }
.hui-alert-success { background: var(--hui-ok-soft); }
.hui-alert-success .hui-alert-icon { background: var(--hui-ok); }
.hui-alert-warning { background: var(--hui-warn-soft); }
.hui-alert-warning .hui-alert-icon { background: var(--hui-warn); }
.hui-alert-danger { background: var(--hui-bad-soft); }
.hui-alert-danger .hui-alert-icon { background: var(--hui-bad); }""",
    "quiz": """\
.hui-quiz {
  border: 1px solid var(--hui-line);
  border-radius: var(--hui-radius);
  background: var(--hui-paper);
  box-shadow: var(--hui-shadow);
  color: var(--hui-ink);
  padding: 16px 18px;
  margin: 10px 0;
}
.hui-quiz-q { font-weight: 700; letter-spacing: 0.01em; margin: 0 0 12px; }
.hui-choice {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--hui-line);
  border-radius: var(--hui-radius-sm);
  padding: 9px 14px;
  margin: 8px 0;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
@media (hover: hover) {
  .hui-choice:hover { border-color: var(--hui-accent); background: var(--hui-accent-soft); }
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
  font-size: 0.9em;
  letter-spacing: 0.02em;
  white-space: nowrap;
}
.hui-choice input:checked ~ .hui-fb { display: inline; }
.hui-is-answer .hui-fb { color: var(--hui-ok-ink); }
.hui-choice:not(.hui-is-answer) .hui-fb { color: var(--hui-bad-ink); }
.hui-choice input:checked + .hui-choice-text { font-weight: 700; }
.hui-is-answer input:checked + .hui-choice-text { color: var(--hui-ok-ink); }
.hui-choice:not(.hui-is-answer) input:checked + .hui-choice-text { color: var(--hui-bad-ink); }
@supports selector(:has(*)) {
  .hui-is-answer:has(input:checked) {
    border-color: var(--hui-ok);
    background: var(--hui-ok-soft);
  }
  .hui-choice:not(.hui-is-answer):has(input:checked) {
    border-color: var(--hui-bad);
    background: var(--hui-bad-soft);
  }
}
.hui-quiz-exp { margin-top: 12px; box-shadow: none; }""",
    "reveal": """\
.hui-reveal {
  border: 1px solid var(--hui-line);
  border-radius: var(--hui-radius);
  background: var(--hui-paper);
  box-shadow: var(--hui-shadow);
  color: var(--hui-ink);
  margin: 10px 0;
  overflow: hidden;
}
.hui-reveal > summary {
  cursor: pointer;
  padding: 11px 16px;
  font-weight: 700;
  letter-spacing: 0.01em;
  color: var(--hui-accent-ink);
  -webkit-user-select: none;
  user-select: none;
}
@media (hover: hover) {
  .hui-reveal > summary:hover { background: var(--hui-accent-soft); }
}
.hui-reveal[open] > summary { border-bottom: 1px solid var(--hui-line); }
.hui-reveal-body { padding: 13px 16px; color: var(--hui-ink-2); }""",
    "progress": """\
.hui-progress { margin: 12px 0; }
.hui-progress-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.92em;
  margin-bottom: 5px;
}
.hui-progress-num { font-weight: 700; color: var(--hui-accent-ink); }
.hui-progress-track {
  height: 12px;
  border-radius: 999px;
  background: var(--hui-bg-2);
  border: 1px solid var(--hui-line);
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
  border: 1px solid var(--hui-line);
  border-radius: var(--hui-radius);
  background: var(--hui-paper);
  box-shadow: var(--hui-shadow);
  color: var(--hui-ink);
  padding: 14px 20px;
  margin: 10px 8px 0 0;
  min-width: 8em;
  vertical-align: top;
}
.hui-stat-label { font-size: 0.85em; color: var(--hui-ink-3); }
.hui-stat-value {
  font-size: 1.9em;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -0.01em;
}
.hui-stat-unit {
  font-size: 0.55em;
  font-weight: 700;
  color: var(--hui-ink-3);
  margin-left: 3px;
}""",
    "columns": """\
.hui-cols {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  margin: 10px 0;
}
.hui-col { flex: 1 1 0; min-width: 200px; }
.hui-col > :first-child { margin-top: 0; }
.hui-col > :last-child { margin-bottom: 0; }
.hui-col > .hui-stat { width: 100%; }""",
    "badge": """\
.hui-badge {
  display: inline-block;
  padding: 2px 12px;
  border-radius: 999px;
  border: 1px solid var(--hui-line);
  background: var(--hui-bg-2);
  color: var(--hui-ink-2);
  font-size: 0.82em;
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1.7;
  margin: 0 4px 4px 0;
}
.hui-badge-blue {
  color: var(--hui-accent-ink);
  background: var(--hui-accent-soft);
  border-color: var(--hui-accent-soft);
}
.hui-badge-green {
  color: var(--hui-ok-ink);
  background: var(--hui-ok-soft);
  border-color: var(--hui-ok-soft);
}
.hui-badge-red {
  color: var(--hui-bad-ink);
  background: var(--hui-bad-soft);
  border-color: var(--hui-bad-soft);
}
.hui-badge-amber {
  color: var(--hui-warn-ink);
  background: var(--hui-warn-soft);
  border-color: var(--hui-warn-soft);
}""",
    # PyHiroba の .output-html table 系（等幅フォント・右揃え・nowrap）に勝つよう、
    # テーブル関連のセレクタは .hui を前置して詳細度を上げている。
    "table": """\
.hui .hui-table-wrap { overflow-x: auto; margin: 10px 0; }
.hui .hui-table {
  border-collapse: collapse;
  min-width: 50%;
  font-family: inherit;
  font-size: 0.95em;
  line-height: 1.7;
  color: var(--hui-ink);
}
.hui .hui-table caption {
  caption-side: top;
  text-align: left;
  font-weight: 700;
  letter-spacing: 0.01em;
  padding: 0 0 8px;
}
.hui .hui-table th, .hui .hui-table td {
  border: 1px solid var(--hui-line);
  padding: 7px 14px;
  text-align: left;
  white-space: normal;
  font-family: inherit;
  font-size: inherit;
}
.hui .hui-table thead th {
  background: var(--hui-bg-2);
  font-weight: 700;
  text-align: left;
}
.hui .hui-table tbody tr:nth-child(even) { background: var(--hui-bg-2); }
@media (hover: hover) {
  .hui .hui-table tbody tr:hover { background: var(--hui-accent-soft); }
}""",
    "stack": """\
.hui-stack { display: flex; flex-direction: column; margin: 10px 0; }
.hui-stack > * { margin: 0; }
.hui-stack > .hui-badge, .hui-stack > .hui-stat { align-self: flex-start; }""",
}
