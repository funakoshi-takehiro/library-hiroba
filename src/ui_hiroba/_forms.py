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

from collections.abc import Sequence
from typing import Callable, Union

from ._core import Widget, esc, esc_attr, unique_name

FieldLike = Union["Field", str]

# 表示したフォームを ID で引けるようにしておく置き場。
# PyHiroba 本体は、ボタンが押されたときに get_form(form_id).submit(**values) を呼ぶ。
# 教材を長く開いたままでも増え続けないよう、古いものから捨てる。
_REGISTRY: dict[str, Form] = {}
_REGISTRY_LIMIT = 64


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
        if kind not in self.KINDS:
            raise ValueError(f"kind は {list(self.KINDS)} のいずれかにしてください（指定値: {kind!r}）")
        if kind == "choice" and not choices:
            raise ValueError("kind='choice' のときは choices を指定してください")
        self.name = name
        self.label = name if label is None else label
        self.placeholder = placeholder
        self.kind = kind
        self.choices = [str(c) for c in choices] if choices else []
        self.default = default

    def control_html(self) -> str:
        """入力欄そのもののマークアップ。"""
        common = f'class="hui-input" data-hui-field="{esc_attr(self.name)}"'
        placeholder = f' placeholder="{esc_attr(self.placeholder)}"' if self.placeholder else ""
        value = esc_attr(self.default) if self.default != "" else ""
        if self.kind == "multiline":
            return f"<textarea {common} rows=\"3\"{placeholder}>{esc(self.default)}</textarea>"
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

    def ask_via_input(self) -> str:
        """``input()`` で1つ聞く（ipywidgets が使えない環境向け）。"""
        hint = f"（{'／'.join(self.choices)}）" if self.kind == "choice" else ""
        return input(f"{self.label}{hint}： ")


def as_field(item: FieldLike) -> Field:
    return item if isinstance(item, Field) else Field(str(item))


class Form(Widget):
    """入力欄とボタンを出し、押されたら ``handler`` を呼ぶ部品。"""

    css_keys = ("form",)

    def __init__(
        self,
        handler: Callable[..., object],
        fields: Sequence[FieldLike],
        submit_label: str = "送信",
        title: object = None,
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

        def on_click(_):
            values = {name: control.value for name, control in controls.items()}
            with output:
                clear_output(wait=True)
                display(self.handler(**values))

        button.on_click(on_click)
        header = [widgets.HTML(f"<b>{esc(self.title)}</b>")] if self.title is not None else []
        display(widgets.VBox([*header, *controls.values(), button, output]))
        return True

    def _run_with_input(self) -> None:
        """``input()`` で順番に聞いて、結果を表示する。"""
        from IPython.display import display

        values = {field.name: field.ask_via_input() for field in self.fields}
        display(self.handler(**values))

    def submit(self, **values: object) -> object:
        """入力値を渡して ``handler`` を呼ぶ。

        PyHiroba 本体が値を受け取ったときに呼ぶ入口でもある。
        自分でテストするときにも使える。
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


def form(handler, *fields, submit_label="送信", title=None) -> Form:
    """入力欄とボタンを表示し、押されたら ``handler`` を呼ぶ。

    ``handler`` は入力欄の name をキーワード引数として受け取り、
    表示したい部品を返す。

    >>> def ask(question):
    ...     return ui.card(question, "答えです")
    >>> ui.form(ask, ui.field("question", label="質問"))

    入力欄は文字列だけでも指定できる（その名前のテキスト欄になる）。

    >>> ui.form(ask, "question")
    """
    return Form(handler, fields, submit_label=submit_label, title=title)
