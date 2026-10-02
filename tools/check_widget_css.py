"""Colab の見た目（ipywidgets 経路）を、実際に描いて測る。

    pip install playwright
    python tools/check_widget_css.py

ipywidgets は入力欄の大きさを決め打ちしている（``--jp-widgets-inline-height: 28px``、
``--jp-widgets-inline-label-width: 80px``）。こちらの CSS がそこへ余白を足すと、
文字の入る高さが残らず**上下が切れる**。名前は 80px の欄に押し込まれて「…」になる。
どちらも例外にならず、Colab で開いた人にしか見えない。

本物の ipywidgets の CSS は JS の束に埋まっているので、そこから取り出して当てる。
通信も Colab も要らないが、ブラウザが要るのでテストからは呼ばない（CI を
ブラウザの都合で落とさないため）。ipywidgets を上げたときに手で回す。

PyHiroba 側（HTML で描く経路）の実測値と突き合わせる。**揃っていることが答え**で、
数字そのものに意味はない。
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from library_hiroba import ui

CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def contrast(foreground: str, background: str) -> float:
    """2色の明暗の差（WCAG）。``rgb(r, g, b)`` の形で受け取る。

    題名は色が完全に一致しなくても読めなくなる（白地に ほぼ白）。
    一致するかではなく、差が足りているかで見る。
    """

    def luminance(color: str) -> float:
        nums = [int(v) / 255 for v in re.findall(r"\d+", color)[:3]]
        parts = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in nums]
        return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def widget_css() -> str:
    """インストール済みの ipywidgets から、本物の CSS を取り出す。"""
    import widgetsnbextension

    bundle = pathlib.Path(widgetsnbextension.__file__).parent / "static" / "extension.js"
    js = bundle.read_text(errors="replace")
    blocks = []
    # 変数の定義（:root）と規則は別の塊に入っている。**定義のほうは値まで含めて
    # 探す**。var(--…) の使用側を拾うと規則の塊を二度取り、変数が無いまま当たって
    # しまい、何も再現していないのに「問題なし」と出る
    for probe in ("--jp-widgets-inline-height: 28px", ".jupyter-widget-dropdown {"):
        index = js.index(probe)
        low, high = index, index
        while low > 0 and js[low] != '"':
            low -= 1
        while high < len(js) - 1 and js[high] != '"':
            high += 1
        text = js[low + 1 : high].encode().decode("unicode_escape")
        # 切り出しは規則の途中から始まるので、最初の規則まで捨てる（残すと
        # 閉じかけのコメントでパーサが止まり、1規則も効かない）
        start = re.search(r"^(:root|\.[A-Za-z])", text, re.M)
        text = text[start.start() :] if start else text
        blocks.append(text[: text.rfind("}") + 1])
    css = "\n".join(blocks)
    if ":root" not in css or "--jp-widgets-inline-label-width" not in css:
        raise RuntimeError("ipywidgets の CSS を取り出せませんでした（束の形が変わった？）")
    return css


def page(our_css: str, dark: bool) -> str:
    """ipywidgets が実際に作る組み立て。旧名と新名の両方を付ける（CSS が別名で宣言）。"""

    def field(label: str, control: str) -> str:
        return (
            '<div class="jupyter-widgets widget-inline-hbox jupyter-widget-inline-hbox '
            'widget-dropdown jupyter-widget-dropdown hui-wfield">'
            f'<label class="widget-label jupyter-widget-label">{label}</label>{control}</div>'
        )

    theme = (
        "<style>:root{--jp-content-font-color1:#e8eaed;--jp-ui-font-color1:#e8eaed}</style>"
        if dark
        else ""
    )
    body = (
        '<div class="jupyter-widgets widget-box widget-vbox jupyter-widget-box '
        'jupyter-widget-vbox hui hui-wform" id="form">'
        f"<style>{our_css}</style>"
        '<div class="jupyter-widgets widget-inline-hbox jupyter-widget-inline-hbox '
        'widget-html jupyter-widget-html"><div class="widget-html-content '
        'jupyter-widget-html-content" id="title"><b>クラスTシャツ色決定</b></div></div>'
        + field("クラス1（Aさんの案）", "<select><option>赤</option></select>")
        + field("クラス2（Bさんの案）", '<input type="text" value="赤">')
        + field("感想（自由に書いてください）", '<textarea rows="3">ここに書く</textarea>')
        + '<button class="jupyter-button widget-button hui-wsubmit" id="submit">決定</button>'
        "</div>"
    )
    return f"<!doctype html><meta charset=utf-8>{theme}<style>{widget_css()}</style>{body}"


MEASURE = """() => {
  const n = (el, p) => parseFloat(getComputedStyle(el)[p]) || 0;
  const inner = el => el.clientHeight - n(el,'paddingTop') - n(el,'paddingBottom');
  const out = {};
  for (const [key, sel] of [["選択欄","select"],["入力欄","input[type=text]"],["複数行","textarea"]]) {
    const el = document.querySelector('.hui-wfield ' + sel);
    out[key] = {高さ: Math.round(el.getBoundingClientRect().height),
                文字の入る高さ: inner(el), 要る高さ: +(n(el,'fontSize')*1.2).toFixed(1)};
  }
  const lab = document.querySelector('.hui-wfield label');
  out["名前"] = {切れている: lab.scrollWidth > lab.clientWidth + 1,
                 幅: Math.round(lab.getBoundingClientRect().width)};
  const btn = document.getElementById('submit'), form = document.getElementById('form');
  out["ボタン"] = {幅: Math.round(btn.getBoundingClientRect().width),
                   枠の幅: Math.round(form.clientWidth)};
  out["題名"] = {色: getComputedStyle(document.getElementById('title')).color,
                 枠の地: getComputedStyle(form).backgroundColor};
  return out;
}"""


def html_path_sizes(page_obj) -> dict:
    """PyHiroba 側（HTML）の実測。Colab 側はここに揃っているべき。"""
    form = ui.form(
        lambda a, b: a,
        ui.field("a", label="クラス1（Aさんの案）"),
        ui.field("b", label="クラス2", kind="choice", choices=["赤", "青"]),
    )
    page_obj.set_content("<!doctype html><meta charset=utf-8>" + form._repr_html_())
    return page_obj.evaluate(
        """() => ({入力欄: Math.round(document.querySelector('input.hui-input').getBoundingClientRect().height),
                   ボタン: Math.round(document.querySelector('.hui-submit').getBoundingClientRect().width)})"""
    )


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright が要ります: pip install playwright")
        return 1
    if not pathlib.Path(CHROMIUM).exists():
        print(f"ブラウザが見つかりません: {CHROMIUM}")
        return 1

    our = ui.form(lambda a: a, ui.field("a"))._widget_style_block()
    our = our.replace("<style>", "").replace("</style>", "")
    problems = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM)
        tab = browser.new_page(viewport={"width": 900, "height": 600})
        html_sizes = html_path_sizes(tab)
        print(f"PyHiroba 側（HTML）: 入力欄 {html_sizes['入力欄']}px / ボタン {html_sizes['ボタン']}px\n")
        for dark in (False, True):
            tab.set_content(page(our, dark))
            # 当たっているかを先に確かめる。当たっていないと、ぶつかり自体が
            # 起きないので**何も測らずに「問題なし」**と出る
            alive = tab.evaluate(
                """() => ({v: getComputedStyle(document.documentElement)
                             .getPropertyValue('--jp-widgets-inline-height').trim(),
                           n: [...document.styleSheets].reduce((a,s)=>{
                                try {return a + s.cssRules.length} catch(e) {return a}}, 0)})"""
            )
            if alive["v"] != "28px" or alive["n"] < 100:
                print(f"★ ipywidgets の CSS が当たっていません（{alive}）。測定できません。")
                return 1
            found = tab.evaluate(MEASURE)
            print(f"--- Colab 側（ipywidgets・{'ダーク' if dark else 'ライト'}）---")
            print(json.dumps(found, ensure_ascii=False, indent=2))
            for key in ("選択欄", "入力欄", "複数行"):
                box = found[key]
                if box["文字の入る高さ"] < box["要る高さ"]:
                    print(f"  ★ {key}: 文字が切れます（{box['文字の入る高さ']}px < {box['要る高さ']}px）")
                    problems += 1
            if found["名前"]["切れている"]:
                print("  ★ 名前が「…」で切れています")
                problems += 1
            if found["ボタン"]["幅"] > found["ボタン"]["枠の幅"] * 0.8:
                print("  ★ ボタンが横いっぱいに伸びています")
                problems += 1
            ratio = contrast(found["題名"]["色"], found["題名"]["枠の地"])
            if ratio < 4.5:
                print(f"  ★ 題名が読めません（地との差 {ratio:.2f}:1、4.5:1 が必要）")
                problems += 1
            if found["選択欄"]["高さ"] != html_sizes["入力欄"]:
                print(f"  ★ PyHiroba 側（{html_sizes['入力欄']}px）と高さが違います")
                problems += 1
            print()
        browser.close()
    print("問題なし" if not problems else f"要確認 {problems} 件")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
