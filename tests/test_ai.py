"""ai の検証。

ブラウザ経路は ``js`` を偽物に差し替えて、PyHiroba 本体との契約
（kind の名前・JSON 文字列でのやり取り・返り値の読み方）を確かめる。
Colab 経路は transformers を偽物に差し替えて、生成パラメータまで確かめる。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
import types

import pytest

import library_hiroba
from library_hiroba import _ai


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def fresh_ai():
    """毎回まっさらな Ai を使う（読み込み状態を持ち越さない）。"""
    return _ai.Ai()


class FakeHost:
    """PyHiroba 本体の js.pyhirobaAsk の代役。呼ばれた内容を記録する。"""

    def __init__(self, replies=None):
        self.calls = []
        self.replies = replies or {}

    async def __call__(self, kind, args_json):
        self.calls.append((kind, args_json))
        return json.dumps(self.replies.get(kind, {}))


@pytest.fixture
def in_browser(monkeypatch):
    """PyHiroba のワーカーの中にいる状態を作る。"""
    host = FakeHost(
        {
            "ai-load": {"message": "準備ができました（…／WebGPUで動きます）", "device": "webgpu"},
            "ai-ask": {"text": "答えです", "ms": 3700, "device": "webgpu"},
            "ai-models": [{"name": "qwen05-q8", "label": "…", "approxMB": 900}],
        }
    )
    js = types.ModuleType("js")
    js.pyhirobaAsk = host
    monkeypatch.setitem(sys.modules, "js", js)
    return host


# --- 遅延読み込み -----------------------------------------------------------


def test_ui_does_not_pull_in_ai(monkeypatch):
    """ui だけを使う環境に AI 側の依存を持ち込まない。"""
    for name in list(sys.modules):
        if name.startswith("library_hiroba"):
            monkeypatch.delitem(sys.modules, name, raising=False)
    import library_hiroba as fresh

    assert not [m for m in sys.modules if m.startswith("library_hiroba.")]
    assert fresh.ui is not None
    assert "library_hiroba._ai" not in sys.modules
    assert fresh.ai is not None
    assert "library_hiroba._ai" in sys.modules


def test_unknown_attribute_raises():
    with pytest.raises(AttributeError):
        getattr(library_hiroba, "nope")  # noqa: B009 — __getattr__ を通すため


# ui 側が import してよいもの。PyHiroba は ui をそのまま同梱して閉じた校内
# ネットワークで動かすため、取りに行く先が増えると成り立たなくなる。増やすときに
# 気付けるよう、ここに並べておく（sys.stdlib_module_names は 3.10 以降にしか無い）。
UI_MAY_IMPORT = {
    "__future__",
    "asyncio",
    "collections",
    "html",
    "inspect",
    "re",
    "secrets",
    "typing",
    # ノートブックのある環境でだけ使う。無ければ使わない作りになっている
    "IPython",
    "ipywidgets",
}


def test_ui_stays_dependency_free():
    """ui 側が、許したもの以外を import していないこと（PyHiroba 同梱の前提）。"""
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "library_hiroba"
    for path in ["ui.py", "_core.py", "_css.py", "_components.py", "_forms.py"]:
        tree = ast.parse((src / path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                assert name in UI_MAY_IMPORT, (
                    f"{path} が、許していないものを import している: {name}"
                    "（増やすなら tests/test_ai.py の UI_MAY_IMPORT と "
                    "docs/PYHIROBA_INTEGRATION.md を更新すること）"
                )


# --- モデル名 ---------------------------------------------------------------


def test_both_naming_schemes_are_accepted():
    """ブラウザ側の -q8 / -q4 付きも、共通の名前も受け付ける。"""
    assert _ai.resolve(None) == ("qwen05", "qwen05-q8")
    assert _ai.resolve("qwen05") == ("qwen05", "qwen05-q8")
    assert _ai.resolve("qwen05-q8") == ("qwen05", "qwen05-q8")
    # 精度まで指定されたらその指定を尊重する
    assert _ai.resolve("qwen05-q4") == ("qwen05", "qwen05-q4")
    assert _ai.resolve("qwen15") == ("qwen15", "qwen15-q4")
    assert _ai.resolve("llmjp150m-q4") == ("llmjp150m", "llmjp150m-q4")


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError, match="選べません"):
        _ai.resolve("gpt-9")


def test_every_browser_variant_maps_to_a_base():
    """本体の一覧（qwen05-q8 / qwen05-q4 / qwen15-q4 / llmjp150m-q4）を全部受けられる。"""
    for key in ["qwen05-q8", "qwen05-q4", "qwen15-q4", "llmjp150m-q4"]:
        base, browser_key = _ai.resolve(key)
        assert base in _ai.MODELS
        assert browser_key == key


def test_models_have_the_same_shape_on_both_paths(fresh_ai, monkeypatch, in_browser):
    browser = run(fresh_ai.models())
    monkeypatch.delitem(sys.modules, "js")
    colab = run(fresh_ai.models())
    assert [m["name"] for m in browser] == [m["name"] for m in colab] == list(_ai.MODELS)
    for entry in browser + colab:
        assert set(entry) == {"name", "label", "approxMB"}
        assert isinstance(entry["approxMB"], int)


# --- ブラウザ経路（PyHiroba 本体との契約） ---------------------------------


def test_load_sends_the_browser_key(fresh_ai, in_browser):
    message = run(fresh_ai.load("qwen05"))
    kind, args = in_browser.calls[0]
    assert kind == "ai-load"
    # 共通の名前で呼ばれても、本体にはブラウザ側の名前を渡す
    assert json.loads(args) == {"model": "qwen05-q8"}
    assert message.startswith("準備ができました")


def test_ask_sends_prompt_and_max_tokens(fresh_ai, in_browser):
    run(fresh_ai.load())
    text = run(fresh_ai.ask("日本の四季について", max_tokens=64))
    kind, args = in_browser.calls[-1]
    assert kind == "ai-ask"
    assert json.loads(args) == {"prompt": "日本の四季について", "max_tokens": 64}
    assert text == "答えです"


def test_ask_loads_first_when_not_loaded(fresh_ai, in_browser):
    run(fresh_ai.ask("質問"))
    assert [kind for kind, _ in in_browser.calls] == ["ai-load", "ai-ask"]


def test_models_sends_null(fresh_ai, in_browser):
    run(fresh_ai.models())
    # models() はモデル表から作るので本体を呼ばない（呼ぶのは load / ask だけ）
    assert in_browser.calls == []


def test_only_the_three_allowed_kinds_are_used(fresh_ai, in_browser):
    run(fresh_ai.load())
    run(fresh_ai.ask("質問"))
    run(fresh_ai.models())
    used = {kind for kind, _ in in_browser.calls}
    assert used <= {"ai-load", "ai-ask", "ai-models"}


def test_arguments_are_json_strings(fresh_ai, in_browser):
    """Pyodide と JS の境界は JSON 文字列だけに保つ。"""
    run(fresh_ai.load())
    run(fresh_ai.ask("質問"))
    for _kind, args in in_browser.calls:
        assert isinstance(args, str)
        json.loads(args)


def test_in_browser_detection(monkeypatch):
    monkeypatch.delitem(sys.modules, "js", raising=False)
    assert _ai.in_browser() is False
    js = types.ModuleType("js")  # js はあるが pyhirobaAsk が無い（素の Pyodide）
    monkeypatch.setitem(sys.modules, "js", js)
    assert _ai.in_browser() is False
    js.pyhirobaAsk = lambda *a: None
    assert _ai.in_browser() is True


# --- Colab 経路 -------------------------------------------------------------


def install_fake_transformers(monkeypatch, dtype_keyword="torch_dtype"):
    """transformers と torch の代役を入れ、pipeline に渡った引数の記録を返す。

    ``dtype_keyword`` で、精度を受け取るキーワード名の違い（transformers 4 の
    ``torch_dtype`` / 5 の ``dtype``）を再現する。
    """
    recorded = {}

    def pipeline(task, model, device, **kwargs):
        recorded["build"] = {"task": task, "model": model, "device": device, **kwargs}

        def run_pipe(messages, **call_kwargs):
            recorded["call"] = {"messages": messages, **call_kwargs}
            return [{"generated_text": [{"role": "assistant", "content": " 生成された文章 "}]}]

        return run_pipe

    # _dtype_keyword は signature を見て決めるので、受け取る名前をここで作り分ける
    pipeline.__signature__ = inspect.Signature(
        [
            inspect.Parameter(name, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            for name in ("task", "model", "device", dtype_keyword)
        ]
    )

    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    torch.float16, torch.float32 = "fp16", "fp32"
    transformers = types.ModuleType("transformers")
    transformers.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.delitem(sys.modules, "js", raising=False)
    return recorded


@pytest.fixture
def fake_transformers(monkeypatch):
    return install_fake_transformers(monkeypatch)


def test_colab_load_uses_the_base_model_id(fresh_ai, fake_transformers):
    message = run(fresh_ai.load("qwen05-q8"))  # ブラウザ側の名前で呼ばれても動く
    assert fake_transformers["build"]["model"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert "準備ができました" in message and "CPU" in message


def test_colab_generation_parameters_are_unchanged(fresh_ai, fake_transformers):
    """生成の設定はブラウザ側と揃えてある。勝手に変えない。"""
    run(fresh_ai.load())
    run(fresh_ai.ask("質問", max_tokens=100))
    call = fake_transformers["call"]
    assert call["temperature"] == 0.3
    assert call["top_p"] == 0.9
    assert call["repetition_penalty"] == 1.15
    assert call["do_sample"] is True
    assert call["return_full_text"] is False
    assert call["max_new_tokens"] == 100
    assert call["messages"] == [{"role": "user", "content": "質問"}]


def test_colab_default_max_tokens(fresh_ai, fake_transformers):
    run(fresh_ai.ask("質問"))
    assert fake_transformers["call"]["max_new_tokens"] == 256


def test_colab_answer_is_extracted_and_trimmed(fresh_ai, fake_transformers):
    assert run(fresh_ai.ask("質問")) == "生成された文章"


def test_colab_reload_of_the_same_model_is_skipped(fresh_ai, fake_transformers):
    run(fresh_ai.load("qwen05"))
    assert run(fresh_ai.load("qwen05")) == "すでに準備できています"


def test_dtype_is_passed_under_the_name_transformers_accepts(fresh_ai, monkeypatch):
    """transformers 5 で torch_dtype は dtype に改名された。

    古い名前でも通るが、実行のたびに非推奨の警告が出て教材の画面が荒れる。
    入っている版が受け取る名前で渡す（実物の transformers 5.14 で確認済み）。
    """
    recorded = install_fake_transformers(monkeypatch, dtype_keyword="dtype")
    run(fresh_ai.load())
    assert recorded["build"]["dtype"] == "fp32"
    assert "torch_dtype" not in recorded["build"]


def test_dtype_falls_back_to_the_old_name_on_transformers_4(fresh_ai, monkeypatch):
    recorded = install_fake_transformers(monkeypatch, dtype_keyword="torch_dtype")
    run(fresh_ai.load())
    assert recorded["build"]["torch_dtype"] == "fp32"
    assert "dtype" not in recorded["build"]


def test_missing_dependencies_explain_what_to_install(fresh_ai, monkeypatch):
    monkeypatch.delitem(sys.modules, "js", raising=False)
    monkeypatch.setitem(sys.modules, "transformers", None)
    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.raises(ImportError, match=r"library-hiroba\[ai\]"):
        run(fresh_ai.load())
