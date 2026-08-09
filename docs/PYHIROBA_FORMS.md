# PyHiroba で入力を Python に戻すための設計

`ui.form()` は Colab・Jupyter では動きますが、PyHiroba では入力を受け取れません。この文書は、PyHiroba 本体に何を足せば動くようになるかをまとめたものです。library-hiroba 側は、本体が対応した時点でそのまま動く形の HTML を出しています。

これは提案であり、採用するかどうかは PyHiroba 側の判断です。

---

## 1. 現状

フォームは表示されますが、ボタンを押しても何も起きません。そのため、次の教材が PyHiroba で作れません。

- AI とのチャット（生徒が質問を打ち、AI が答える）
- 入力を受け取って処理する演習全般（計算、判定、アンケート）

`ui` の表示部品と `ai` の文章生成は PyHiroba でも動きます。足りないのは、画面の入力を Python に渡す道です。

## 2. なぜ今は動かないか（実測に基づく事実）

| 調べたこと | 結果 |
|---|---|
| `js/pyodide-worker.js` の stdin | 実装がありません。`input()` は使えません |
| セルの実行方式 | セル全体を同期実行し、終わってから出力を返します。途中で止めて入力を待つ経路がありません |
| 出力 → ワーカーの通信路 | ありません（`app.exec.js` は結果を一方向に描画します） |

出力の中にどのような HTML を置いても、値が Python に戻る道がありません。

### SharedArrayBuffer は使えません

ワーカーを止めて入力を待つためによく使われる `Atomics.wait` と `SharedArrayBuffer` は、`COOP` / `COEP` の HTTP ヘッダーが必要です。PyHiroba は GitHub Pages で配信しておりヘッダーを付けられません（`js/theme.js` にも同じ理由の記述があります）。この方式は選べません。

## 3. 提案する方式: コールバック

セルの実行を止めるのではなく、フォームを表示していったんセルを終え、押されたときに登録しておいた Python の関数を呼び直します。同期実行の作りを変えずに済みます。

```
[セル実行]  Python: フォームを表示し、関数を登録
             ↓ 出力（HTML）
[画面]      利用者が入力してボタンを押す
             ↓ postMessage（本体の JS が送る）
[ワーカー]   登録された関数を値付きで呼ぶ
             ↓ 戻り値の _repr_html_()
[画面]      フォームの下の出力欄を差し替える
```

## 4. サニタイザは変更不要（実測済み）

DOMPurify 3.4.12 に、PyHiroba の `sanitizeHtml()` と同じ設定で通した結果です。

| 要素・属性 | 結果 |
|---|---|
| `data-hui-*` 属性 | そのまま残ります |
| `<input type="text">`、`<textarea>`、`<select>`、`<option>` | 残ります |
| `<button type="button">` | 残ります |
| `name` / `value` / `placeholder` 属性 | 残ります |
| `<form>` | 除去されます（今回は使いません） |

サニタイザの設定を緩める必要はありません。禁止しているものは禁止したまま実現できます。

## 5. library-hiroba が出す HTML の約束

`ui.form()` は次の目印を付けた HTML を出します。本体はこれを手がかりに動きます。

```html
<div class="hui-form" data-hui-form="hui-form-0bb1e225" data-hui-clear="true">
  <label class="hui-field">
    <span class="hui-field-label">質問</span>
    <input class="hui-input" data-hui-field="question" type="text" value="">
  </label>
  <button class="hui-submit" type="button" data-hui-submit="hui-form-0bb1e225">送信</button>
  <div class="hui-form-out" data-hui-output="hui-form-0bb1e225"></div>
</div>
```

| 目印 | 意味 |
|---|---|
| `data-hui-form="ID"` | フォーム全体。ID はセルをまたいで一意です |
| `data-hui-field="名前"` | 入力欄。この名前がそのまま Python の関数のキーワード引数になります |
| `data-hui-submit="ID"` | 押しボタン。クリックを拾う対象です |
| `data-hui-output="ID"` | 結果を差し込む空の場所 |
| `data-hui-clear="true"` | 付いている場合は、送信後に入力欄を空にしてください。付いていない場合はそのままにします |

## 6. 本体に必要な変更

### 6-1. メインスレッド側（`js/app.exec.js`）

イベントの登録は、サニタイズされた出力の中ではなく、本体の信頼できるコードが行います。出力側は目印を置くだけで、動作を持ちません。

```js
// 出力を挿入した直後に呼ぶ
function bindHuiForms(container) {
  container.querySelectorAll('[data-hui-submit]').forEach((button) => {
    button.addEventListener('click', () => {
      const formId = button.getAttribute('data-hui-submit');
      const root = container.querySelector(`[data-hui-form="${CSS.escape(formId)}"]`);
      const values = {};
      root.querySelectorAll('[data-hui-field]').forEach((el) => {
        values[el.getAttribute('data-hui-field')] = el.value;   // 常に文字列で構いません
      });
      worker.postMessage({ type: 'hui-submit', formId, values });
      if (root.hasAttribute('data-hui-clear')) {
        root.querySelectorAll('[data-hui-field]').forEach((el) => {
          if (el.tagName !== 'SELECT') el.value = '';
        });
      }
    });
  });
}
```

戻ってきた HTML は `data-hui-output` の中に入れる前に、通常の出力と同じ `sanitizeHtml()` を通してください。

### 6-2. ワーカー側（`js/pyodide-worker.js`）

フォーム ID から Python 側のフォームを引き、`submit` のメッセージで呼び出します。引く口は library-hiroba が用意します（`library_hiroba.ui.get_form(form_id)`。見つからなければ `None`）。

```python
import inspect

from library_hiroba import ui


async def hui_submit(form_id, values, send_html):
    form = ui.get_form(form_id)
    if form is None:
        return

    # 押した直後に「考え中」を出す（Colab と同じ見た目のものが返ります）
    pending = form.pending_html()
    if pending:
        send_html(pending)

    result = form.submit(**values)

    # handler が async def のとき
    if inspect.isawaitable(result):
        result = await result

    # handler が yield で書かれているとき（AI の答えを少しずつ出す教材）
    if inspect.isasyncgen(result):
        async for item in result:
            send_html(item._repr_html_())
        return

    send_html(result._repr_html_())
```

`handler` の書き方は3つあり、すべてに対応が必要です。

| 書き方 | 返るもの | 対応 |
|---|---|---|
| `def` | 部品 | そのまま `_repr_html_()` を呼びます |
| `async def` | awaitable | `await` してから `_repr_html_()` を呼びます |
| `async def` + `yield` | 非同期の反復子 | 回しながら、届くたびに表示を差し替えます |

`await` を忘れると `_repr_html_()` が失敗します。3つめは、AI の答えを書けたところから見せる教材で使います。

### 6-3. 値の型について（対応は不要です）

ブラウザの入力欄から取れるのは文字列ですが、Colab の ipywidgets は数値欄で `float` を返します。この差は library-hiroba の `submit()` が吸収しますので、本体は `el.value` をそのまま送ってください。`ui.field("age", kind="number")` に `"10"` を送れば、`handler` には `10.0` が渡ります。

種類に合わない値（数値欄に「じゅう」など）を送った場合は、どの欄が問題かを含む `ValueError` になります。その内容を出力欄に表示すると、書いた人が原因を追えます。

## 7. 安全性について

| 心配な点 | この設計での扱い |
|---|---|
| 出力の HTML が勝手に動くのではないか | 動きません。イベントを登録するのは本体のコードで、出力側は `data-*` の目印を持ちます |
| 教材が任意の JavaScript を実行できるのではないか | できません。サニタイザの設定は変更せず、`<script>` もイベント属性も禁止のままです |
| 値の受け渡しでコードが実行されるのではないか | されません。渡るのは `postMessage` の文字列で、呼び出し先は Python 側が自分で登録した関数に限られます |
| 別の教材のフォームを乗っ取れるのではないか | できません。ID は実行のたびに一意で、辞書に登録されたものが引けます |
| 無限に登録されて重くならないか | library-hiroba 側で最大 64 件に制限しています。セルを消したときや再実行のときは、本体側でも対応する登録を消してください |

## 8. 決めていただきたいこと

1. 引く口を `library_hiroba.ui.get_form(form_id)` にするか、本体側で好みの名前（`__hui_forms__` のような辞書）に合わせるか
2. 結果の差し替え先を `data-hui-output` にするか、セルの出力全体を描き直すか
3. フォームの登録をいつ捨てるか（セル削除時、再実行時、ノートブックを閉じたとき）
4. `await` と非同期の反復子を処理する場所を、本体のどこに置くか

これらが決まれば、library-hiroba 側は登録の口を合わせるだけで対応できます。

## 9. 補足: AI の逐次出力（任意）

`ai.stream()` を使うと、答えを書けたところから受け取れます。本体の対応は任意です。`ai-ask-start` と `ai-ask-next` を本体が知らない場合は、既存の `ai-ask` に自動で切り替わり、全文が一度に返ります。受け渡しの形は [`PYHIROBA_INTEGRATION.md`](PYHIROBA_INTEGRATION.md) にあります。
