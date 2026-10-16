"""``ui.html()`` のゲートと、実ブラウザの HTML の読み方を突き合わせる。

    pip install playwright
    python tools/check_parser_parity.py

``dangerous_html()`` は Python の ``html.parser.HTMLParser`` に判定を任せている。
HTMLParser と本物のブラウザは**同じ文字列を別の形に読む**ことがあり、そこを突かれると
危険な書き方が検査を一つも通らずにすり抜ける。Colab にはサニタイザが無いので、
すり抜けたものはそのまま動く。

「検査が何も見つけない」かつ「ブラウザが本物のタグを組み立てて JS を走らせる」
組み合わせが**すり抜け**。逆に、ブラウザも動かさないものを止めてしまうのは過検知で、
こちらは教材が書けなくなるので同じくらい困る。

通信も Colab も要らないが、ブラウザが要るのでテストからは呼ばない（CI をブラウザの
都合で落とさないため）。Python を上げたときや、ゲートを触ったときに手で回す。
``<!-->`` と ``<![CDATA[>`` の取りこぼしはこれで見つけた。
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from library_hiroba._components import dangerous_html

CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

# 走ったことが外から分かる形にする。alert だと止まってしまう
MARK = '<img src=x onerror="window.HITS=(window.HITS||0)+1">'

CASES = {
    "素の onerror（対照・止まるべき）": MARK,
    "<!--> 空コメントが即閉じる": f"<!-->{MARK}-->",
    "<!---> 空コメントが即閉じる": f"<!--->{MARK}-->",
    "--!> でコメントが終わる": f"<!-- x --!>{MARK}",
    "<![CDATA[ は偽コメント": f"<![CDATA[x]]>{MARK}",
    # HTML では <![ は「最初の > で終わる偽コメント」。Python は ]]> を探すので、
    # ]]> の無い書き方で食い違う。長いあいだ空いていた穴がここだった
    "<![CDATA[ の直後に >": f"<![CDATA[>{MARK}",
    "<![CDATA[ の中に > だけ": f"<![CDATA[a>b{MARK}",
    "<!--> と <![CDATA[ の合わせ技": f"<!--><![CDATA[>{MARK}",
    "<![CDATA[ に ]]> も > も無い": f"<![CDATA[{MARK}",
    "<! の直後に >": f"<!>{MARK}",
    "<? の直後に >": f"<?>{MARK}",
    "</ の直後に >": f"</>{MARK}",
    "<!DOCTYPE が閉じない": f"<!DOCTYPE{MARK}",
    "<?php は偽コメント": f"<?php x ?>{MARK}",
    "<![x]> は偽コメント": f"<![x]>{MARK}",
    "</% は不正な終了タグ": f"</%>{MARK}",
    "<!--! の直後": f"<!--!>{MARK}",
    "<!- - は不完全": f"<!- ->{MARK}",
    "IE の条件付きコメント": f"<!--[if IE]>{MARK}<![endif]-->",
    "通常コメントの中（対照・止めなくてよい）": f"<!-- {MARK} -->",
    "コメントの中に --> がある": f"<!-- a --> {MARK} <!-- b -->",
    "<!doctype のあと": f"<!DOCTYPE html>{MARK}",
}


def main() -> int:
    from playwright.sync_api import sync_playwright

    scratch = pathlib.Path(__file__).resolve().parent / "_parity.html"
    rows = []
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_page()
            for name, payload in CASES.items():
                found = dangerous_html(payload)
                scratch.write_text(
                    "<!doctype html><meta charset=utf-8><div id=host>" + payload + "</div>",
                    encoding="utf-8",
                )
                page.goto("file://" + str(scratch))
                page.wait_for_timeout(120)
                ran = bool(page.evaluate("window.HITS || 0"))
                page.evaluate("window.HITS = 0")
                rows.append((name, bool(found), ran))
            browser.close()
    finally:
        scratch.unlink(missing_ok=True)

    print(f"{'書き方':42s} {'検知':>5s} {'ブラウザで動く':>8s}  判定")
    print("-" * 84)
    leaks, over = [], []
    for name, found, ran in rows:
        if ran and not found:
            verdict = ">>> すり抜け"
            leaks.append(name)
        elif ran:
            verdict = "検知できている"
        elif found:
            verdict = ">>> 過検知（教材が書けなくなる）"
            over.append(name)
        else:
            verdict = "どちらも動かない"
        print(f"{name:42s} {found!s:>5s} {ran!s:>8s}  {verdict}")

    print()
    if leaks:
        print("すり抜け:", "、".join(leaks))
    if over:
        print("過検知:", "、".join(over))
    if not leaks and not over:
        print("問題なし")
    return 1 if (leaks or over) else 0


if __name__ == "__main__":
    raise SystemExit(main())
