"""``ui.sketch()`` の出す箱が、実物のブラウザで「動くこと」と「出られないこと」を確かめる。

``ui.sketch()`` の安全は ``sandbox`` 属性だけで成り立っている。Python のテストでは
属性の文字列しか見られないので、ブラウザが本当にそのとおり止めるかはここで測る。
あわせて、無いと**黙って死ぬ** ``alert`` と ``<form>`` の submit が動くことも見る。

使い方: python tools/check_sketch_browser.py
通信は要らない（about:blank に出力を流し込むだけ）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library_hiroba import ui

CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

# 箱の中で動かす JS。できたこと・止められたことを window.R に並べる。
PROBE_JS = """
window.R = [];
function probe(label, fn) {
  try { window.R.push([label, String(fn())]) }
  catch (e) { window.R.push([label, 'ブロック ' + e.name]) }
}
probe('canvas に描ける', () => {
  const ctx = document.querySelector('canvas').getContext('2d');
  ctx.fillStyle = '#028DAE'; ctx.fillRect(0, 0, 40, 20);
  return ctx.getImageData(1, 1, 1, 1).data[2] > 100 ? 'ok' : 'ng';
});
probe('requestAnimationFrame', () => typeof requestAnimationFrame);
probe('fetch がある', () => typeof fetch);
probe('alert が出る', () => { alert('やあ'); return 'ok' });
probe('confirm のもどり値', () => confirm('いい？'));
probe('prompt のもどり値', () => prompt('なまえ'));
probe('親の DOM を書き換える', () => { parent.document.body.innerHTML = 'のっとり'; return 'とどいた' });
probe('親の変数を読む', () => 'よめた→' + parent.SECRET);
probe('localStorage', () => { localStorage.setItem('a', '1'); return 'つかえた' });
probe('cookie', () => document.cookie === '' ? '空' : 'みえた');
probe('親を別ページへ飛ばす', () => { top.location = 'https://example.com/'; return 'させられた' });
probe('自分の origin', () => String(origin));
document.querySelector('form').addEventListener('submit', (e) => {
  e.preventDefault(); window.R.push(['form の submit', 'ハンドラが呼ばれた']);
});
setTimeout(() => document.querySelector('button').click(), 50);
"""

# 「こうなっていなければおかしい」という期待。前半は動くこと、後半は出られないこと。
EXPECTED = {
    "canvas に描ける": "ok",
    "requestAnimationFrame": "function",
    "fetch がある": "function",
    "alert が出る": "ok",
    "confirm のもどり値": "true",
    "prompt のもどり値": "はなこ",
    "form の submit": "ハンドラが呼ばれた",
    "親の DOM を書き換える": "ブロック SecurityError",
    "親の変数を読む": "ブロック SecurityError",
    "localStorage": "ブロック SecurityError",
    "cookie": "ブロック SecurityError",
    "親を別ページへ飛ばす": "ブロック SecurityError",
    "自分の origin": "null",
}


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright が入っていません: pip install playwright")
        return 2

    widget = ui.sketch(
        '<canvas width="40" height="20"></canvas><form><button type="submit">送る</button></form>',
        js=PROBE_JS,
        height=160,
    )
    # 親のページに「盗られたら分かるもの」を置いてから、ライブラリの出力を挿す
    page_html = (
        "<!doctype html><meta charset='utf-8'><body>"
        "<script>window.SECRET='ひみつ';document.body.dataset.mark='もとのまま'</script>"
        f"{widget._repr_html_()}</body>"
    )

    with sync_playwright() as play:
        browser = play.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page()
        dialogs: list[str] = []

        def on_dialog(dialog):
            dialogs.append(dialog.type)
            if dialog.type == "prompt":
                dialog.accept("はなこ")
            else:
                dialog.accept()

        page.on("dialog", on_dialog)
        page.set_content(page_html)
        page.wait_for_timeout(1200)
        report = dict(page.frames[-1].evaluate("() => window.R || []"))
        parent_mark = page.evaluate("document.body.dataset.mark")
        parent_secret = page.evaluate("window.SECRET")
        parent_url = page.url
        browser.close()

    problems = 0
    print("箱の中からの報告")
    for label, want in EXPECTED.items():
        got = report.get(label, "(報告なし)")
        ok = got == want
        if not ok:
            problems += 1
        print(f"  {'   ' if ok else ' ★ '}{label:24} {got}" + ("" if ok else f"   ← 期待: {want}"))

    print("\n親のページ")
    for label, got, want in (
        ("body", parent_mark, "もとのまま"),
        ("SECRET", parent_secret, "ひみつ"),
        ("URL", parent_url, "about:blank"),
    ):
        ok = got == want
        if not ok:
            problems += 1
        print(f"  {'   ' if ok else ' ★ '}{label:8} {got}" + ("" if ok else f"   ← 期待: {want}"))

    print(f"\n実際に出たダイアログ: {dialogs or '出ていない'}")
    print("問題なし" if problems == 0 else f"★ {problems} 件おかしい")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
