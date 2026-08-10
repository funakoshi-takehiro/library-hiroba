"""Colab で ui.form() の送信が動かないとき、どの層で止まっているかを調べる。

**このファイルは実行するものではなく、貼るものです。** ipywidgets はノートブックの
セルの中でしか動かないため、下の CELL を Colab のセルにそのまま貼って実行してください。

    !pip install -q library-hiroba
    # このファイルの CELL の中身を貼って実行

調べるのは4つで、どれも「押しても何も起きない」の原因になりえます。

1. 押下処理が呼ばれているか
2. その中でイベントループが回っているか（ここが display_result の分岐を決める）
3. ループに載せたタスクが実際に走るか
4. Output ウィジェットへの3通りの書き込みのうち、どれが画面に出るか

4 が要点です。library-hiroba は ``outputs`` への代入を使っています。Colab で
これが出ないなら、書き込み方を変える必要があります。

分かったこと（Colab / ipywidgets 7.7.1 / Python 3.12 での実測）
--------------------------------------------------------------

1. 押下処理は呼ばれる
2. ``asyncio.get_running_loop()`` は ``running=True`` のループを返す
3. **そのループに載せたタスクは走らない**
4. Output への書き込みは A・B・C のどれも画面に届く

つまり詰まっていたのは書き込み方ではなく、**予約したタスクが動かないこと**
でした。Colab はセルの実行が終わっているあいだループを回しておらず、押下から
``ensure_future`` したタスクは順番待ちのまま止まります。ループが ``running=True``
と答えるので、外からは見分けが付きません。

0.5.1 から、ipywidgets 経路では自前のループを別スレッドで回しています
（``_forms.run_detached``）。この確認ツールは、同じ症状が別の環境で出たときの
切り分けのために残してあります。
"""

CELL = '''
# --- ui.form() の送信が止まる場所を調べる ------------------------------------
import asyncio, sys
import ipywidgets as widgets
from IPython.display import display

log = widgets.Output()
report = []


def note(text):
    report.append(text)
    log.outputs = ({"output_type": "stream", "name": "stdout",
                    "text": "\\n".join(report) + "\\n"},)


# 3通りの書き込み先を別々に用意して、どれが画面に出るか目で見る
by_outputs = widgets.Output()
by_context = widgets.Output()
by_handle_box = widgets.Output()

button = widgets.Button(description="調べる")


def on_click(_):
    report.clear()
    note("1. 押下処理は呼ばれた")

    try:
        loop = asyncio.get_running_loop()
        note(f"2. ループは回っている: {loop!r}")
        running = True
    except RuntimeError as error:
        note(f"2. ループは回っていない: {error}")
        running = False

    # 3通りの書き込み
    by_outputs.outputs = ({"output_type": "display_data",
                           "data": {"text/html": "<b>A: outputs への代入</b>"},
                           "metadata": {}},)
    with by_context:
        display(widgets.HTML("<b>B: with output: display()</b>"))
    with by_handle_box:
        display(widgets.HTML("<b>C: 取っ手つき display()</b>"))
    note("3. A・B・C を書き込んだ（下に出たものが、その環境で使える方法）")

    async def later():
        await asyncio.sleep(0.5)
        note("4. ループに載せたタスクが走った")
        by_outputs.outputs = ({"output_type": "display_data",
                               "data": {"text/html": "<b>A': タスクからの outputs 代入</b>"},
                               "metadata": {}},)

    if running:
        task = asyncio.ensure_future(later())
        globals()["_keep"] = task          # 参照を持たないと回収されうる
        note("4. タスクを予約した（0.5秒後に結果が出るか見る）")
    else:
        asyncio.run(later())


button.on_click(on_click)
print("ipywidgets", widgets.__version__, "/ Python", sys.version.split()[0])
display(widgets.VBox([button, log, by_outputs, by_context, by_handle_box]))
'''


if __name__ == "__main__":
    print(__doc__)
    print("=" * 70)
    print(CELL)
