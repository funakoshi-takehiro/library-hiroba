# PyHiroba で入力を Python に戻すための設計案

`ui.form()` は Colab では動きますが、PyHiroba では入力を受け取れません。この文書は、PyHiroba 本体に何を足せば動くようになるかをまとめたものです。library-hiroba 側はすでに、本体が対応した時点でそのまま動く形の HTML を出しています。

これは提案であり、採用するかどうかは PyHiroba 側の判断です。

---

## 1. なぜ今は動かないか（実測に基づく事実）

| 調べたこと | 結果 |
|---|---|
| `js/pyodide-worker.js` の stdin | 実装がありません。`input()` は使えません |
| セルの実行方式 | セル全体を同期実行し、終わってから出力を返します。途中で止めて入力を待つ経路がありません |
| 出力 → ワーカーの通信路 | ありません（`app.exec.js` は結果を一方向に描画するだけです） |

そのため、出力の中にどんな HTML を置いても、値が Python に戻る道がありません。

### SharedArrayBuffer は使えません

「ワーカーを止めて入力を待つ」ためによく使われる `Atomics.wait` + `SharedArrayBuffer` は、`COOP` / `COEP` の HTTP ヘッダーが必要です。PyHiroba は GitHub Pages で配信しておりヘッダーを付けられません（`js/theme.js` にも同じ理由の記述があります）。したがって、この方式は選べません。

## 2. 選んだ方式: コールバック方式

セルの実行を止めるのではなく、**「フォームを表示して、いったんセルを終える」→「押されたら、登録しておいた Python の関数を呼び直す」** という2段階にします。同期実行の作りを変えずに済みます。

```
[セル実行]  Python: フォームを表示し、関数を登録
             ↓ 出力（HTML）
[画面]      利用者が入力してボタンを押す
             ↓ postMessage（本体の JS が送る）
[ワーカー]   登録された関数を値付きで呼ぶ
             ↓ 戻り値の _repr_html_()
[画面]      フォームの下の出力欄を差し替える
```

## 3. サニタイザは変更不要（実測済み）

DOMPurify 3.4.12 に、PyHiroba の `sanitizeHtml()` と同じ設定で通した結果です。

| 要素・属性 | 結果 |
|---|---|
| `data-hui-*` 属性 | そのまま残ります |
| `<input type="text">`、`<textarea>`、`<select>`、`<option>` | 残ります |
| `<button type="button">` | 残ります |
| `name` / `value` / `placeholder` 属性 | 残ります |
| `<form>` | 除去されます（今回は使いません） |

つまり **サニタイザの設定を緩める必要はありません**。禁止しているものは禁止したまま実現できます。

## 4. library-hiroba が出す HTML の約束

`ui.form()` は次の目印を付けた HTML を出します。本体はこれを手がかりに動きます。

```html
<div class="hui-form" data-hui-form="hui-form-1a2b3c4d">
  <label class="hui-field">
    <span class="hui-field-label">質問</span>
    <input class="hui-input" data-hui-field="question" type="text" value="">
  </label>
  <button class="hui-submit" type="button" data-hui-submit="hui-form-1a2b3c4d">送信</button>
  <div class="hui-form-out" data-hui-output="hui-form-1a2b3c4d"></div>
</div>
```

| 目印 | 意味 |
|---|---|
| `data-hui-form="ID"` | フォーム全体。ID はセルをまたいで一意です |
| `data-hui-field="名前"` | 入力欄。この名前がそのまま Python の関数のキーワード引数になります |
| `data-hui-submit="ID"` | 押しボタン。クリックを拾う対象です |
| `data-hui-output="ID"` | 結果を差し込む空の場所 |

## 5. 本体に必要な変更

### 5-1. ワーカー側（`js/pyodide-worker.js`）

フォーム ID から Python 側のフォームを引き、`submit` のメッセージで呼び出します。引く口は library-hiroba が用意します（`library_hiroba.ui.get_form(form_id)`。見つからなければ `None`）。

```python
# ワーカーの中で（Python 側）
import inspect

from library_hiroba import ui

async def hui_submit(form_id, values):
    form = ui.get_form(form_id)
    if form is None:
        return None
    result = form.submit(**values)
    # handler が async def のときは、返り値が待つもの（awaitable）になる
    if inspect.isawaitable(result):
        result = await result
    return result._repr_html_()
```

**`await` が要る点にご注意ください。** `ai.ask()` を呼ぶ handler は `async def` で書くことになり、`submit()` の返り値はコルーチンになります。await せずに `_repr_html_()` を呼ぶと失敗します。

### 5-2. メインスレッド側（`js/app.exec.js`）

**ここが要点です。** イベントの登録は、サニタイズされた出力の中ではなく、**本体の信頼できるコードが行います**。出力側は目印を置くだけで、動作は一切持ちません。

```js
// 出力を挿入した直後に呼ぶ
function bindHuiForms(container) {
  container.querySelectorAll('[data-hui-submit]').forEach((button) => {
    button.addEventListener('click', () => {
      const formId = button.getAttribute('data-hui-submit');
      const root = container.querySelector(`[data-hui-form="${CSS.escape(formId)}"]`);
      const values = {};
      root.querySelectorAll('[data-hui-field]').forEach((el) => {
        values[el.getAttribute('data-hui-field')] = el.value;
      });
      worker.postMessage({ type: 'hui-submit', formId, values });
    });
  });
}
```

結果を受け取ったら、`data-hui-output` の中身を `sanitizeHtml()` に通してから差し替えます。**戻ってきた HTML も、通常の出力と同じサニタイズを通してください。**

## 6. 安全性について

| 心配な点 | この設計での扱い |
|---|---|
| 出力の HTML が勝手に動くのでは | 動きません。イベントを登録するのは本体のコードだけで、出力側は `data-*` の目印を持つだけです |
| 教材が任意の JavaScript を実行できるのでは | できません。サニタイザの設定は変更せず、`<script>` もイベント属性も禁止のままです |
| 値の受け渡しでコードが実行されるのでは | されません。渡るのは `postMessage` の文字列だけで、呼び出し先は Python 側が自分で登録した関数に限られます |
| 別の教材のフォームを乗っ取れるのでは | できません。ID は実行のたびに一意で、辞書に登録されたものだけが引けます |
| 無限に登録されて重くならないか | セルを消したときや再実行のときに、対応する登録を消してください |

## 7. 決めていただきたいこと

1. 引く口を `library_hiroba.ui.get_form(form_id)` にするか、本体側で好みの名前（`__hui_forms__` のような辞書）に合わせるか
2. 結果の差し替え先を `data-hui-output` にするか、セルの出力全体を描き直すか
3. フォームの登録をいつ捨てるか（セル削除時、再実行時、ノートブックを閉じたとき）
4. `submit()` の返り値が awaitable のときに await する処理を、本体のどこに置くか（フォームから `ai` を呼ぶ教材で必要になります）

これらが決まれば、library-hiroba 側は登録の口を合わせるだけで対応できます。
