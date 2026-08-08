"""全部品のギャラリー HTML を生成し、``--shots`` でスクリーンショットも撮る。

生成物（tools/out/）:

- ``gallery-light.html``      明るいホスト（Colab ライト相当）
- ``gallery-dark.html``       ``data-theme="dark"`` なホスト（PyHiroba ダーク相当）
- ``gallery-dark-media.html`` 属性なしの暗いホスト（OS ダーク相当。スクショ時に
  ``prefers-color-scheme: dark`` をエミュレートしてメディアクエリ層を検証する）
- ``*.png``                   上記のスクリーンショット（quiz は正解/不正解を
  選んだ状態を再現して撮る）

各ウィジェットの ``_repr_html_()`` をそのまま連結する — セルごとに ``<style>``
が重複挿入される PyHiroba の実態と同じ条件で描画するため。
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import ui_hiroba as ui  # noqa: E402
from ui_hiroba._css import FONT_IMPORT  # noqa: E402

OUT = ROOT / "tools" / "out"

GOOGLE_FONTS_CSS = (
    "https://fonts.googleapis.com/css2?"
    "family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap"
)
# Chromium はサンドボックス内から Google Fonts へ直接出られないため、
# ビルド時に @font-face 一式をローカルへ取得してスクリーンショットで実際の
# 書体を確認できるようにする（ライブラリ本体は @import のままで変更しない）。
UA_WOFF2 = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def fetch_local_font_css() -> bool:
    """Zen Kaku Gothic New をローカルへ取得して out/fonts.css を書く。失敗したら False。"""
    fonts_dir = OUT / "fonts"
    try:
        req = urllib.request.Request(GOOGLE_FONTS_CSS, headers={"User-Agent": UA_WOFF2})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (固定URL)
            css = resp.read().decode("utf-8")
        fonts_dir.mkdir(parents=True, exist_ok=True)
        for i, url in enumerate(dict.fromkeys(re.findall(r"url\((https://[^)]+\.woff2)\)", css))):
            name = f"zenkaku-{i}.woff2"
            with urllib.request.urlopen(  # noqa: S310 (取得済み CSS 内の URL)
                urllib.request.Request(url, headers={"User-Agent": UA_WOFF2}), timeout=30
            ) as fr:
                (fonts_dir / name).write_bytes(fr.read())
            css = css.replace(url, f"fonts/{name}")
        (OUT / "fonts.css").write_text(css, encoding="utf-8")
        return True
    except Exception as exc:  # ネットワークが無い環境では system-ui で撮る
        print(f"  (フォント取得をスキップ: {exc})")
        return False


def demo_widgets() -> list[tuple[str, ui.Widget]]:
    return [
        (
            "card",
            ui.card(
                "今日の目標",
                "for文を使って、九九の表を作ってみよう！\n終わったら手を挙げて教えてね。",
                footer="ヒント: range(1, 10) を2回使うよ",
            ),
        ),
        (
            "alert（4種類）",
            ui.stack(
                ui.alert("インデントはスペース4つで揃えよう"),
                ui.alert("実行できたね！次の問題に進もう", kind="success"),
                ui.alert("range(5) は 0〜4 まで。5 は入らないよ", kind="warning", title="よくあるまちがい"),
                ui.alert("保存せずに閉じると作業が消えます", kind="danger"),
            ),
        ),
        (
            "quiz（スクショでは正解を選択済み）",
            ui.quiz(
                "2の8乗はいくつ？",
                choices=[128, 256, 512],
                answer=256,
                explanation="2を8回かけると 256 になるよ。Python では 2**8 で計算できる。",
            ),
        ),
        (
            "quiz（スクショではまちがいを選択済み）",
            ui.quiz("リストの最初の要素は？", choices=["a[0]", "a[1]", "a.first()"], answer="a[0]"),
        ),
        ("reveal", ui.reveal("print('こんにちは') と書きます", summary="答えを見る")),
        (
            "progress",
            ui.stack(
                ui.progress(7, max=10, label="練習問題の進み具合"),
                ui.progress(100, label="今日の目標", show_value=True),
            ),
        ),
        (
            "stat + columns",
            ui.columns(
                ui.stat("正答率", 85, unit="%"),
                ui.stat("れんぞく正解", 4, unit="問"),
                ui.stat("学習時間", 25, unit="分"),
            ),
        ),
        (
            "badge（5色）",
            ui.stack(
                ui.badge("NEW"),
                ui.badge("クリア", color="green"),
                ui.badge("重要", color="red"),
                ui.badge("チャレンジ", color="amber"),
                ui.badge("メモ", color="gray"),
                gap="4px",
            ),
        ),
        (
            "table",
            ui.table(
                [
                    {"名前": "佐藤", "得点": 90, "コメント": "よくできました"},
                    {"名前": "鈴木", "得点": 85, "コメント": "おしい！"},
                    {"名前": "高橋", "得点": 78, "コメント": "あと少し"},
                ],
                caption="漢字テストの結果",
            ),
        ),
        (
            "html + css（自由記述・CSS は既定で自動スコープ）",
            ui.stack(
                ui.html(
                    '<div class="fukidashi">こんにちは！<br>いっしょに <b>Python</b> を勉強しよう</div>',
                    css="""
.fukidashi {
  display: inline-block;
  border: 2px solid var(--hui-accent);
  border-radius: 14px;
  padding: 10px 16px;
  background: var(--hui-accent-soft);
  font-weight: 700;
}
b { color: var(--hui-accent-ink); }
""",
                ),
                ui.html("<p>となりの部品の <b>太字</b> はスコープ外なので影響を受けない</p>"),
            ),
        ),
        (
            "組み合わせ（columns の中に card）",
            ui.columns(
                ui.card("ステップ1", "変数に数を入れる"),
                ui.card("ステップ2", "print で表示する"),
            ),
        ),
    ]


def page(title: str, body_style: str, html_attr: str = "") -> str:
    sections = []
    for name, widget in demo_widgets():
        # 部品 CSS の Google Fonts @import は、外部へ出られない環境だと読み込みが
        # 止まってしまう。ギャラリーではローカルの fonts.css が同じ書体を供給する
        # ので、この一行だけ取り除く（ライブラリ本体の出力は変更しない）。
        rendered = widget._repr_html_().replace(FONT_IMPORT, "")
        sections.append(f"<section><h2>{name}</h2>\n{rendered}\n</section>")
    joined = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html{html_attr}>
<head>
<meta charset="utf-8">
<title>ui-hiroba gallery — {title}</title>
<link rel="stylesheet" href="fonts.css">
<style>
  body {{ {body_style} font-family: 'Zen Kaku Gothic New', system-ui, sans-serif;
         font-feature-settings: "palt"; -webkit-font-smoothing: antialiased;
         max-width: 860px; margin: 0 auto; padding: 24px; line-height: 1.7; }}
  h1 {{ font-size: 20px; font-weight: 900; letter-spacing: -0.01em; }}
  h2 {{ font-size: 13px; opacity: 0.6; font-weight: 700; margin: 28px 0 4px;
       border-bottom: 1px solid rgba(127, 127, 127, 0.25); padding-bottom: 2px; }}
</style>
</head>
<body>
<h1>ui-hiroba gallery — {title}</h1>
{joined}
</body>
</html>
"""


# 背景色は PyHiroba のセル出力領域の実値（ライト #fafaf8 / ダーク #151a20）に合わせる
PAGES = {
    "gallery-light.html": page(
        "light（PyHiroba / Colab ライト相当）", "background: #fafaf8; color: #101418;"
    ),
    "gallery-dark.html": page(
        "dark（PyHiroba ダーク相当・data-theme）",
        "background: #151a20; color: #e8eaed;",
        html_attr=' data-theme="dark"',
    ),
    "gallery-dark-media.html": page(
        "dark（OS ダーク相当・prefers-color-scheme）",
        "background: #1e1e1e; color: #d4d4d4;",
    ),
}


def build_pages() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, content in PAGES.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"wrote {OUT / name}")


def take_screenshots(font_ready: bool) -> None:
    from playwright.sync_api import sync_playwright

    shots = [
        # (ファイル, エミュレートする配色設定, 出力名)
        ("gallery-light.html", "light", "light.png"),
        ("gallery-dark.html", "light", "dark-datatheme.png"),
        ("gallery-dark-media.html", "dark", "dark-media.png"),
    ]
    # Web フォント（Zen Kaku Gothic New）取得のため、環境にプロキシがあれば使う。
    # 取得できない環境では system-ui にフォールバックしたまま撮影される。
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for file, scheme, out_name in shots:
            tab = browser.new_page(viewport={"width": 880, "height": 1000}, color_scheme=scheme)
            # 部品 CSS の @import は外部へ出られない環境で読み込みを止めてしまうため、
            # 外部リクエストは遮断する（書体はローカルの fonts.css から供給される）
            tab.route("http://**", lambda route: route.abort())
            tab.route("https://**", lambda route: route.abort())
            tab.goto((OUT / file).as_uri())
            if font_ready:
                tab.wait_for_function(
                    "document.fonts.check('700 16px \\'Zen Kaku Gothic New\\'')", timeout=15000
                )
            quizzes = tab.locator(".hui-quiz")
            quizzes.nth(0).locator("input").nth(1).check()  # 正解（256）を選ぶ
            quizzes.nth(1).locator("input").nth(1).check()  # まちがい（a[1]）を選ぶ
            tab.locator(".hui-reveal").nth(1).click()  # reveal を開いた状態で撮る
            tab.wait_for_timeout(150)
            tab.screenshot(path=str(OUT / out_name), full_page=True)
            tab.close()
            print(f"wrote {OUT / out_name}")
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", action="store_true", help="Playwright でスクリーンショットも撮る")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    font_ready = fetch_local_font_css()
    build_pages()
    if args.shots:
        take_screenshots(font_ready)


if __name__ == "__main__":
    main()
