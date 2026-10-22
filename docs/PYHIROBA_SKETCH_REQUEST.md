# お願い: `ui.sketch()`（JavaScript の動く枠）への対応

`library-hiroba` 0.10.0 に `ui.sketch()` を足しました。授業で canvas のお絵かきや
ゲーム、自作 API を叩くところまで扱えるようにするためのものです。

**お願いするのは、ワーカーから返った HTML を挿したあとに走らせる JS を6行足すことだけです。
サニタイザ（`sanitizeHtml`）の設定は、1文字も変えなくて済みます。**

- [1. 足していただくもの](#1-足していただくもの)
- [2. なぜこの形なのか（ほかの道が無い）](#2-なぜこの形なのか)
- [3. 安全性 — 実物のブラウザで測った結果](#3-安全性--実物のブラウザで測った結果)
- [4. `sandbox` の3つの値について](#4-sandbox-の3つの値について)
- [5. 確かめ方](#5-確かめ方)
- [6. 対応しない場合](#6-対応しない場合)

## 1. 足していただくもの

### 1-1. `pyhirobaFeatures` に `sketch` を足す

```js
self.pyhirobaFeatures = 'forms,ai,ai-probe,sketch'
```

これが無いあいだ、library-hiroba は箱の代わりに
「いまお使いの PyHiroba ではまだ動きません」という注意書きを出します。
**名乗っていないのに下の JS を足しても、箱は出ません**（こちらが出さないので）。

### 1-2. 出力を挿した直後に、箱を組む

`bindHuiForms(container)` を呼んでいるのと同じ場所で、続けて呼んでください。

```js
const HUI_SKETCH_SANDBOX = 'allow-scripts allow-modals allow-forms'

function bindHuiSketches(container) {
  container.querySelectorAll('[data-hui-sketch]').forEach((box) => {
    const frame = document.createElement('iframe')
    frame.setAttribute('sandbox', HUI_SKETCH_SANDBOX)
    frame.setAttribute('title', 'JavaScript の動く枠')
    frame.srcdoc = new TextDecoder().decode(
      Uint8Array.from(atob(box.getAttribute('data-hui-sketch')), (ch) => ch.charCodeAt(0)))
    box.removeAttribute('data-hui-sketch')
    box.replaceChildren(frame)
  })
}
```

library-hiroba が出すのはこれだけです（`<iframe>` は出しません）。

```html
<div class="hui-sketch hui-sketch-3f9a1c2e" data-hui-sketch="PCFkb2N0eXBlIGh0bWw+…"></div>
```

- 中身は**1枚の HTML**（`<!doctype html>` から `</html>` まで）を UTF-8 で base64 に
  したものです。`atob` のあと `TextDecoder` を通すのは、日本語が入るためです
- 箱の高さは `<style>` の中に `.hui-sketch-3f9a1c2e { height: 240px }` の形で入れて
  あります。`iframe` 側は `height: 100%` にしてあるので、**先に場所が取られ、
  `iframe` が入った瞬間に下の表示がずれません**
- `data-hui-sketch` は組んだあと消してください（二重に組まないため）

**`sandbox` の値を付けるのは本体側です。** こちらからは渡していません。そうすると、
悪意のあるノートブックが `allow-same-origin` を混ぜ込む余地がありません。

## 2. なぜこの形なのか

「`<script>` を出す」「`<iframe srcdoc>` を出す」のどちらも**成立しません**。
DOMPurify 3.4.12 で測った結果です。

| 出してみたもの | サニタイズ後 |
|---|---|
| `<script>alert(1)</script>` | `""`（消える） |
| `<div><script>…</script></div>` | `<div></div>` |
| `<button onclick="…">` | `onclick` だけ消える |
| `<iframe sandbox="…" srcdoc="&lt;b&gt;x&lt;/b&gt;">` | `srcdoc` が残る |
| `<iframe sandbox="…" srcdoc="…&lt;script&gt;…">` | **`srcdoc` ごと消える** |
| `<div data-hui-sketch="…&lt;script&gt;…">` | **属性ごと消える** |
| `<div data-hui-sketch="PCFkb2N0…">`（base64） | **そのまま残る** |

`srcdoc` が消えるのは、DOMPurify が属性値に `</script` `</style` `-->` などが
入っているものを落とすためです（`SAFE_FOR_XML`、`purify.es.mjs` の該当行）。
これは**フックより手前**の検査なので、`uponSanitizeAttribute` で
`forceKeepAttr = true` にしても残せません（試しました）。`data-*` 属性も
同じ検査にかかるため、`</script` を含まない形＝base64 にしています。

さらに、本体は出力を `innerHTML` で挿しています。**`innerHTML` に入れた
`<script>` は仕様上そもそも実行されません**（これも実測）。つまりサニタイザを
緩めていただいても、それだけでは動きません。

残る唯一の道が、**別の document に閉じ込めてブラウザ自身の隔離に守らせる**ことです。

## 3. 安全性 — 実物のブラウザで測った結果

Chromium 1194 で、親のページに `window.SECRET` と目印を置いた状態で、
箱の中から手を伸ばしてみた結果です。

| 箱の中からやったこと | 結果 |
|---|---|
| `parent.document.body.innerHTML = …` | **ブロック**（SecurityError） |
| `parent.SECRET` を読む | **ブロック**（SecurityError） |
| `localStorage` / `sessionStorage` | **ブロック**（SecurityError） |
| `document.cookie` | **ブロック**（SecurityError） |
| `top.location = 'https://…'` | **ブロック**（SecurityError） |
| `window.open(…)` | `null` |
| 自分の `origin` | `null`（不透明オリジン） |
| `canvas` に描く | 動く |
| `setTimeout` / `requestAnimationFrame` | 動く |
| `fetch` | 使える（CORS は通常どおり効きます） |

測ったあと、親のページの目印も `window.SECRET` も URL も変わっていません。

**効いているのは「`allow-same-origin` を入れていないこと」1点だけです。**
入れると箱は親と同じオリジンになり、上のブロックが**全部とれます**。
`HUI_SKETCH_SANDBOX` にこれを足さないでください。

残るリスクは次のとおりで、いずれも隔離の外には出ません。

- 箱の中に本物らしい入力欄を描いて入力をうながす（箱の中で完結しますが、
  画面上はページの一部に見えます）
- `fetch` や `<img>` で外部へ通信する（これは**いまでも** `ui.html()` の
  `<img src="https://…">` でできることです）
- 重い処理でそのタブを遅くする

## 4. `sandbox` の3つの値について

`allow-scripts` だけでは足りません。残り2つが無いと**黙って死ぬ**ものがあり、
しかもエラーが一切出ないためです（実測）。

| 無いとどうなるか | |
|---|---|
| `alert('やあ')` | 例外も出さずに**無反応**。JS でいちばん最初に書かれるのがこれです |
| `confirm(…)` | つねに `false` |
| `prompt(…)` | つねに `null` |
| `<form>` の送信 | `addEventListener('submit', …)` が**呼ばれない** |

`allow-modals` と `allow-forms` はこれを直すためだけに入れています。
`allow-modals` を入れると、箱がダイアログを連続で出してそのタブを
操作しづらくすることはできます（Chrome は「このページでこれ以上ダイアログを
表示しない」を出します）。**そこを避けたいという判断なら外していただいて構いません。**
その場合は値を教えてください。こちら側は「`alert` は使えない」と案内に書き換えます
（黙って無反応のままにはしません）。

## 5. 確かめ方

| 見たいこと | やりかた |
|---|---|
| 箱が組まれるか | PyHiroba のセルで `ui.sketch('<canvas width="300" height="150"></canvas>', js="const c=document.querySelector('canvas').getContext('2d'); c.fillStyle='tomato'; c.fillRect(10,10,120,60)")` |
| 名乗る前の見え方 | `pyhirobaFeatures` から `sketch` を外すと、注意書きに変わります |
| 隔離が効いているか | `python tools/check_sketch_browser.py`（こちらのリポジトリ。実物の Chromium で上の表を測り直します） |
| サニタイザを通っても欠けないか | こちらで測りました。**設定そのままで、失われた文字数 0** |

こちら側は 651 テスト＋変異テスト8件で固定してあります（`sandbox` の値を
ライブラリと検査の両方が同じ値で持っていること、`allow-same-origin` が
出力に出ないこと、未対応の本体で iframe を出さないこと、など）。

## 6. 対応しない場合

**何も起きません。** `sketch` を名乗らないあいだ、`ui.sketch()` は箱の代わりに
「いまお使いの PyHiroba ではまだ動きません。Colab では動きます」という
注意書きを出します。既存の部品も `ai` も影響を受けません。

急ぎません。教材を作る側には「JS を使う教材は当面 Colab で」と案内します。
