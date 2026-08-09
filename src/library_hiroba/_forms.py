"""入力を受け取って Python の関数に渡すためのフォーム。

環境によって使える経路が違うため、次の順で自動的に選ぶ。

1. ipywidgets がある（Colab / Jupyter）… テキスト欄とボタンの対話 UI
2. IPython があり ipywidgets が無い … ``input()`` で順番に聞く
3. PyHiroba の受け渡し経路がある … HTML のフォームを出し、本体が値を返す
4. どれも無い … フォームを表示だけして、書きかえて実行する方法を案内する

3 の経路は PyHiroba 本体（出力からワーカーへ値を渡すしくみ）が必要で、
その仕様は docs/PYHIROBA_FORMS.md にまとめてある。ここで出す HTML は、
本体が対応した時点でそのまま動くように ``data-hui-*`` を付けてある。
"""

from __future__ import annotations

import asyncio
import inspect
import keyword
from collections.abc import Sequence
from typing import Callable, Union

from ._core import Widget, esc, esc_attr, unique_name

FieldLike = Union["Field", str]

# 表示したフォームを ID で引けるようにしておく置き場。
# PyHiroba 本体は、ボタンが押されたときに get_form(form_id).submit(**values) を呼ぶ。
# 教材を長く開いたままでも増え続けないよう、古いものから捨てる。
_REGISTRY: dict[str, Form] = {}
_REGISTRY_LIMIT = 64

# 表示待ちの処理。回収されないよう、終わるまでここで持つ（display_result 参照）
_PENDING: set = set()


def get_form(form_id: str) -> Form | None:
    """表示済みのフォームを ID で取り出す。見つからなければ ``None``。

    PyHiroba 本体から呼ぶための入口。詳しくは docs/PYHIROBA_FORMS.md を参照。
    """
    return _REGISTRY.get(form_id)


def _register(form: Form) -> None:
    _REGISTRY[form.form_id] = form
    while len(_REGISTRY) > _REGISTRY_LIMIT:
        _REGISTRY.pop(next(iter(_REGISTRY)))


class Field:
    """フォームの入力欄1つぶんの指定。"""

    KINDS = ("text", "number", "choice", "multiline")

    def __init__(
        self,
        name: str,
        label: str | None = None,
        placeholder: str = "",
        kind: str = "text",
        choices: Sequence[object] | None = None,
        default: object = "",
    ):
        if not name.isidentifier():
            raise ValueError(f"name は Python の変数名として使える文字にしてください（指定値: {name!r}）")
        # class・for・if などは変数名の形をしているが、handler の引数にはできない。
        # ここで止めないと、ボタンを押した時点で初めて TypeError になり、
        # 書いた本人には何が悪いのか分からない。
        if keyword.iskeyword(name):
            raise ValueError(
                f"name に Python の予約語は使えません（指定値: {name!r}）。"
                f"handler の引数にできないためです。{name}_ のように少し変えてください。"
            )
        if kind not in self.KINDS:
            raise ValueError(f"kind は {list(self.KINDS)} のいずれかにしてください（指定値: {kind!r}）")
        if kind == "choice" and not choices:
            raise ValueError("kind='choice' のときは choices を指定してください")
        self.name = name
        self.label = name if label is None else label
        self.placeholder = placeholder
        self.kind = kind
        self.choices = [str(c) for c in choices] if choices else []
        # 選択欄で default を書かなかった場合は最初の選択肢にする。
        # 指定しないと ipywidgets は未選択（handler が None を受け取る）、
        # HTML の select は先頭が選択済みとなり、経路で結果がずれる。
        if kind == "choice" and str(default) not in self.choices:
            default = self.choices[0]
        self.default = default

    def control_html(self) -> str:
        """入力欄そのもののマークアップ。"""
        common = f'class="hui-input" data-hui-field="{esc_attr(self.name)}"'
        placeholder = f' placeholder="{esc_attr(self.placeholder)}"' if self.placeholder else ""
        value = esc_attr(self.default) if self.default != "" else ""
        if self.kind == "multiline":
            # ここは esc（改行を <br> にする）を使わない。textarea の中身はタグとして
            # 解釈されないので、<br> がそのまま「<br>」という文字で見えてしまう。
            return f"<textarea {common} rows=\"3\"{placeholder}>{esc_attr(self.default)}</textarea>"
        if self.kind == "choice":
            options = "".join(
                f'<option value="{esc_attr(c)}"'
                f'{" selected" if str(self.default) == c else ""}>{esc(c)}</option>'
                for c in self.choices
            )
            return f"<select {common}>{options}</select>"
        input_type = "number" if self.kind == "number" else "text"
        return f'<input {common} type="{input_type}" value="{value}"{placeholder}>'

    def fragment(self) -> str:
        return (
            f'<label class="hui-field"><span class="hui-field-label">{esc(self.label)}</span>'
            f"{self.control_html()}</label>"
        )

    def convert(self, raw: str) -> object:
        """``input()`` で受け取った文字列を、この欄の型に合わせる。

        ipywidgets 経路は数値欄で float を返すため、``input()`` 経路も
        揃えないと同じコードの計算結果が変わってしまう。
        """
        if self.kind == "number":
            return float(raw)
        if self.kind == "choice" and raw not in self.choices:
            raise ValueError(f"{'／'.join(self.choices)} のどれかを入力してください")
        return raw

    def ask_via_input(self, attempts: int = 3) -> object:
        """``input()`` で1つ聞く（ipywidgets が使えない環境向け）。

        入力が型に合わないときは聞き直す。それでも合わなければ例外にする。
        """
        hint = f"（{'／'.join(self.choices)}）" if self.kind == "choice" else ""
        for remaining in range(attempts - 1, -1, -1):
            raw = input(f"{self.label}{hint}： ")
            try:
                return self.convert(raw)
            except ValueError as error:
                if remaining == 0:
                    raise ValueError(f"{self.label}: {error}") from None
                message = error if self.kind == "choice" else "数を入力してください"
                print(f"  {message}（あと{remaining}回）")
        raise AssertionError("到達しない")


def as_field(item: FieldLike) -> Field:
    return item if isinstance(item, Field) else Field(str(item))


def display_result(result: object, into: object = None) -> None:
    """``handler`` の返り値を表示する。

    ``ai.ask()`` を呼ぶ handler は ``async def`` で書くことになり、返り値は
    ``await`` してからでないと中身が取れない。そのまま表示するとコルーチン
    オブジェクトが出てしまうため、待ってから表示する。

    ``into`` に ipywidgets の Output を渡すと、その中に表示する（待っている
    あいだにセルの実行が終わっても、結果がフォームの下に出るようにするため）。
    """
    from IPython.display import display

    if not inspect.isawaitable(result):
        display(result)
        return

    async def wait_then_show() -> None:
        # await は Output の中で行う。handler が途中で失敗したときに、
        # その内容がフォームの下にそのまま表示されるようにするため。
        if into is None:
            display(await result)
        else:
            with into:
                display(await result)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # ノートブックの外（素の Python）。回っているループが無いので自分で回す
        asyncio.run(wait_then_show())
    else:
        # ノートブックの中。ループに載せて、終わったときに表示する。
        # 参照を持たないと、待っている最中に回収されて結果が出ないことがある
        # （ループはタスクを弱参照でしか持たない）。AI の返事は数秒かかるので、
        # 終わるまで手元で持っておき、終わったら捨てる。
        task = asyncio.ensure_future(wait_then_show())
        _PENDING.add(task)
        task.add_done_callback(_PENDING.discard)


class Form(Widget):
    """入力欄とボタンを出し、押されたら ``handler`` を呼ぶ部品。"""

    css_keys = ("form",)

    def __init__(
        self,
        handler: Callable[..., object],
        fields: Sequence[FieldLike],
        submit_label: str = "送信",
        title: object = None,
        clear_on_submit: bool = False,
    ):
        if not callable(handler):
            raise ValueError("handler には関数を渡してください")
        if not fields:
            raise ValueError("入力欄を1つ以上渡してください")
        self.handler = handler
        self.fields = [as_field(f) for f in fields]
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            raise ValueError(f"入力欄の name が重複しています: {names}")
        self.submit_label = submit_label
        self.title = title
        self.clear_on_submit = clear_on_submit
        self.form_id = unique_name("hui-form")

    # --- 表示 ---------------------------------------------------------------

    def fragment(self) -> str:
        title = (
            f'<div class="hui-form-title">{esc(self.title)}</div>' if self.title is not None else ""
        )
        rows = "".join(f.fragment() for f in self.fields)
        return (
            f'<div class="hui-form" data-hui-form="{esc_attr(self.form_id)}">'
            f"{title}{rows}"
            f'<button class="hui-submit" type="button" '
            f'data-hui-submit="{esc_attr(self.form_id)}">{esc(self.submit_label)}</button>'
            f'<div class="hui-form-out" data-hui-output="{esc_attr(self.form_id)}"></div>'
            f"</div>"
        )

    def _repr_html_(self) -> str:
        # PyHiroba 経路（IPython が無い環境）ではこちらが使われる。
        # 本体がボタンの押下を受け取ったときに引けるよう、ここで登録する。
        _register(self)
        return super()._repr_html_()

    def _ipython_display_(self) -> None:
        """IPython のある環境（Colab など）での表示。

        ipywidgets があれば対話 UI、無ければ ``input()`` で聞く。
        """
        if self._display_with_ipywidgets():
            return
        self._run_with_input()

    # --- 経路ごとの実装 -----------------------------------------------------

    def _build_ipywidgets(self):
        """ipywidgets の部品を組み立てる。使えない場合は None。"""
        try:
            import ipywidgets as widgets
        except ImportError:
            return None
        controls = {}
        for field in self.fields:
            label = field.label
            if field.kind == "choice":
                controls[field.name] = widgets.Dropdown(
                    options=field.choices,
                    value=str(field.default) if str(field.default) in field.choices else None,
                    description=label,
                )
            elif field.kind == "number":
                controls[field.name] = widgets.FloatText(
                    value=float(field.default or 0), description=label
                )
            elif field.kind == "multiline":
                controls[field.name] = widgets.Textarea(
                    value=str(field.default), placeholder=field.placeholder, description=label
                )
            else:
                controls[field.name] = widgets.Text(
                    value=str(field.default), placeholder=field.placeholder, description=label
                )
        return widgets, controls

    def _display_with_ipywidgets(self) -> bool:
        built = self._build_ipywidgets()
        if built is None:
            return False
        widgets, controls = built
        from IPython.display import clear_output, display

        button = widgets.Button(description=self.submit_label, button_style="primary")
        output = widgets.Output()

        clearable = {f.name for f in self.fields if f.kind in ("text", "multiline")}

        def on_click(_):
            values = {name: control.value for name, control in controls.items()}
            if self.clear_on_submit:
                for name in clearable:
                    controls[name].value = ""
            with output:
                clear_output(wait=True)
                display_result(self.handler(**values), into=output)

        button.on_click(on_click)
        header = [widgets.HTML(f"<b>{esc(self.title)}</b>")] if self.title is not None else []
        display(widgets.VBox([*header, *controls.values(), button, output]))
        return True

    def _run_with_input(self) -> None:
        """``input()`` で順番に聞いて、結果を表示する。"""
        values = {field.name: field.ask_via_input() for field in self.fields}
        display_result(self.handler(**values))

    def submit(self, **values: object) -> object:
        """入力値を渡して ``handler`` を呼ぶ。

        PyHiroba 本体が値を受け取ったときに呼ぶ入口でもある。
        自分でテストするときにも使える。

        ``handler`` が ``async def`` のときは、返り値が待つもの（awaitable）に
        なる。呼び出し側で ``await`` してから表示すること。
        """
        missing = [f.name for f in self.fields if f.name not in values]
        if missing:
            raise ValueError(f"入力値が足りません: {missing}")
        return self.handler(**values)


def field(name, label=None, placeholder="", kind="text", choices=None, default="") -> Field:
    """フォームの入力欄を1つ作る。

    >>> ui.field("question", label="質問", placeholder="スマホは持っていっていい？")
    >>> ui.field("size", label="大きさ", kind="choice", choices=["小", "中", "大"])
    """
    return Field(
        name, label=label, placeholder=placeholder, kind=kind, choices=choices, default=default
    )


def form(handler, *fields, submit_label="送信", title=None, clear_on_submit=False) -> Form:
    """入力欄とボタンを表示し、押されたら ``handler`` を呼ぶ。

    ``handler`` は入力欄の name をキーワード引数として受け取り、
    表示したい部品を返す。

    >>> def ask(question):
    ...     return ui.card(question, "答えです")
    >>> ui.form(ask, ui.field("question", label="質問"))

    入力欄は文字列だけでも指定できる（その名前のテキスト欄になる）。

    >>> ui.form(ask, "question")
    """
    return Form(
        handler,
        fields,
        submit_label=submit_label,
        title=title,
        clear_on_submit=clear_on_submit,
    )
