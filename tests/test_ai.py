"""ai の検証。

ブラウザ経路は ``js`` を偽物に差し替えて、PyHiroba 本体との契約
（kind の名前・JSON 文字列でのやり取り・返り値の読み方）を確かめる。
Colab 経路は transformers を偽物に差し替えて、生成パラメータまで確かめる。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import sys
import threading
import time
import types

import pytest
from conftest import require_torch
from sanitize_check import check_html

import library_hiroba
from library_hiroba import _ai


def run(coro):
    return asyncio.run(coro)


def pinned(make):
    """``from_pretrained`` の代役。``revision`` を渡されなければ落ちる。

    ここを ``lambda repo, revision=None`` のように省略できる形で書くと、本体から
    ``revision=`` を外しても代役が黙って受け取ってしまい、**版の固定が消えたことに
    どのテストも気付かない**。キーワード必須にして、外したら落ちるようにしておく。
    """

    def from_pretrained(repo, *, revision):
        return make(repo, revision)

    return from_pretrained


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
    "keyword",
    "re",
    "secrets",
    # ipywidgets 経路だけで使う（Colab のループは押下処理から予約したタスクを
    # 走らせないため、自前のループを別スレッドで回す）。PyHiroba には IPython も
    # ipywidgets も無いのでその経路に入らず、Pyodide でスレッドは作らない。
    # 読み込み自体も関数の中まで遅らせてある
    "threading",
    "traceback",
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


def _bare_model_name(repo: str) -> str:
    """配布元と ONNX の印を落として、モデル本体の名前だけにする。

    ``Qwen/Qwen2.5-0.5B-Instruct`` も
    ``onnx-community/Qwen2.5-0.5B-Instruct`` も ``qwen2.5-0.5b-instruct`` になる。
    """
    name = repo.split("/")[-1].lower()
    # 落としてよいのは**書き出しの形式を表す印だけ**。instruct2 / instruct3 のような
    # 版の違いは落とさない（落とすとこの検査の意味が無くなる）。
    #
    # ``-text`` は onnx-community が「テキスト塔だけを書き出した」ことを表す印で、
    # Qwen3.5 0.8B がこれに当たる。本家が同じモデルかどうかは実際に突き合わせた:
    #   - hidden_size / layers / heads / kv_heads / intermediate / vocab /
    #     max_position / rms_norm_eps の8項目がすべて一致
    #   - チャットテンプレートが 7755 文字で完全一致（sha256 273d8e0e683b8850）
    # 文章しか扱わないこのライブラリでは、両者は同じ重みを見ている。
    for mark in ("-onnx", "_onnx", "-text"):
        if name.endswith(mark):
            name = name[: -len(mark)]
    return name


@pytest.mark.parametrize("name", sorted(_ai.MODELS))
def test_both_paths_load_the_same_model(name):
    """Colab とブラウザで、同じ名前から同じモデルが読まれること。

    「同じコードが両方で動く」の中身。片方だけ版を上げると、利用者は同じ名前を
    書いたのに違うモデルが動く。instruct3 と instruct2 を取り違えた実績がある
    ので、名前の一致を機械で確かめる。
    """
    spec = _ai.MODELS[name]
    colab = _bare_model_name(spec["colab_id"])
    browser = _bare_model_name(spec["browser_repo"])
    assert colab == browser, (
        f"{name} が環境でずれています: Colab は {spec['colab_id']}、"
        f"ブラウザは {spec['browser_repo']}"
    )


@pytest.mark.parametrize("name", sorted(_ai.MODELS))
def test_every_model_records_where_it_comes_from(name):
    """本体側が変換元を選び直せないよう、両方の配布元を必ず書いておく。"""
    spec = _ai.MODELS[name]
    assert "/" in spec["colab_id"], "Colab 側は 配布元/名前 の形で書くこと"
    assert "/" in spec["browser_repo"], "ブラウザ側は 配布元/名前 の形で書くこと"


@pytest.mark.parametrize("name", sorted(_ai.MODELS))
def test_every_model_says_what_it_needs(name):
    """モデルを増やしたとき、おすすめの判断材料を書き忘れないこと。"""
    spec = _ai.MODELS[name]
    assert isinstance(spec["rank"], int)
    assert set(spec["needs"]) == {"browser", "colab"}
    assert set(spec["needs"]["browser"]) == {"webgpu", "memory_gb", "storage_mb"}
    assert set(spec["needs"]["colab"]) == {"ram_gb", "vram_gb"}


@pytest.mark.parametrize("name", sorted(_ai.MODELS))
def test_the_recommended_precision_is_one_we_offer(name):
    """``browser_key`` は必ず ``browser_variants`` の中から選ぶこと。

    ここがずれると本体の知らない名前が渡り、ブラウザでだけ読み込みに失敗する
    （Colab には精度の区別が無いので、手元のテストでは気付けない）。
    先頭を推奨の精度にしておく。
    """
    spec = _ai.MODELS[name]
    assert spec["browser_key"] in spec["browser_variants"]
    assert spec["browser_variants"][0] == spec["browser_key"], (
        f"{name}: 推奨の精度を browser_variants の先頭に置くこと"
    )


@pytest.mark.parametrize("name", sorted(_ai.MODELS))
def test_the_recommended_precision_is_not_the_biggest_download(name):
    """推奨の精度が、選べる中でいちばん重いものになっていないこと。

    ``qwen3_06`` では 4bit のほうが大きい（877MB）。q4 は MatMul だけを 4bit に
    し、埋め込みは fp32 で残すためで、語彙 151936 の Qwen3 ではそこが効く。
    「4bit なら軽いはず」で q4 に戻すと、利用者の通信量が 1.5 倍になる。
    """
    spec = _ai.MODELS[name]
    if spec["browser_key"].endswith("-q4") and f"{name}-q8" in spec["browser_variants"]:
        pytest.fail(
            f"{name}: q8 も選べるのに q4 を推奨している。"
            "このモデルでは 8bit のほうが小さく精度も高いか、確かめること"
        )


def test_the_quality_order_has_no_ties():
    """順位が重なると「いちばん良いもの」が呼ぶたびに変わりかねない。"""
    ranks = [spec["rank"] for spec in _ai.MODELS.values()]
    assert len(set(ranks)) == len(ranks), f"rank が重複しています: {sorted(ranks)}"


def test_the_lightest_model_runs_without_webgpu():
    """WebGPU の無い端末でも1つは動くこと（何も薦められない環境を作らない）。"""
    assert _ai.MODELS[_ai._SAFEST]["needs"]["browser"]["webgpu"] is False
    assert _ai.MODELS[_ai._SAFEST]["needs"]["colab"]["vram_gb"] is None


# --- 考えている途中を隠す ---------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("<think>まず数える</think>答えは3です", "答えは3です"),
        ("<think>あ</think>\n\n答え", "答え"),
        ("<think>1</think>A<think>2</think>B", "AB"),
        ("<think>改行を\nまたぐ</think>答え", "答え"),
        # 字数が尽きて閉じられなかった。考えの途中は見せない
        ("<think>まだ考えている途中で", ""),
        ("答えは3です<think>続きを考え", "答えは3です"),
        # 考えないモデルの出力は素通し
        ("ふつうの答え", "ふつうの答え"),
        ("", ""),
    ],
)
def test_thinking_is_hidden(raw, expected):
    assert _ai.strip_thinking(raw) == expected


def test_stripping_twice_changes_nothing():
    """本体が削ったあとに、こちらでもう一度通しても壊れない。"""
    once = _ai.strip_thinking("<think>考え</think>答え")
    assert _ai.strip_thinking(once) == once == "答え"


def test_browser_path_hides_thinking_even_if_the_host_forgets(fresh_ai, in_browser):
    """本体が削り忘れても、利用者に見える文章は Colab 経路と同じになる。"""
    in_browser.replies["ai-ask"] = {"text": "<think>考え</think>答えは3です"}
    assert run(fresh_ai.ask("2+1は？")) == "答えは3です"


class _FakeTokenizer:
    """``enable_thinking`` を受け付けるテンプレート。"""

    def __init__(self) -> None:
        self.seen: dict | None = None

    def apply_chat_template(self, messages, **kwargs):
        self.seen = kwargs
        return "<|im_start|>" + messages[-1]["content"]


class _OldTokenizer:
    """``enable_thinking`` を知らない古いテンプレート。"""

    def apply_chat_template(self, messages, **kwargs):
        if "enable_thinking" in kwargs:
            raise TypeError("enable_thinking なんて知らない")
        return "古い形式"


def _pipe_with(tokenizer):
    def pipe(prompt, **kwargs):
        pipe.given = prompt
        return [{"generated_text": "<think>考え</think>答え"}]

    pipe.tokenizer = tokenizer
    return pipe


def test_thinking_models_are_asked_not_to_think(fresh_ai):
    tokenizer = _FakeTokenizer()
    fresh_ai._pipe = _pipe_with(tokenizer)
    fresh_ai._name = "qwen3_06"  # has_thinking のモデル

    assert fresh_ai._ask_with_transformers("2+1は？", None) == "答え"
    assert tokenizer.seen["enable_thinking"] is False
    assert tokenizer.seen["add_generation_prompt"] is True


def test_old_templates_fall_back_to_plain_messages(fresh_ai):
    """``enable_thinking`` が通らない版でも、削り取りだけで同じ結果になる。"""
    fresh_ai._pipe = _pipe_with(_OldTokenizer())
    fresh_ai._name = "qwen3_06"

    assert fresh_ai._ask_with_transformers("2+1は？", None) == "答え"
    # テンプレートを諦めたので、会話の形のまま渡っている
    assert fresh_ai._pipe.given == [{"role": "user", "content": "2+1は？"}]


def test_models_without_thinking_are_left_alone(fresh_ai):
    """考えないモデルにテンプレートを差し込まない（余計なことをしない）。"""
    tokenizer = _FakeTokenizer()
    fresh_ai._pipe = _pipe_with(tokenizer)
    fresh_ai._name = "qwen05"

    fresh_ai._ask_with_transformers("2+1は？", None)
    assert tokenizer.seen is None
    assert fresh_ai._pipe.given == [{"role": "user", "content": "2+1は？"}]


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


# 本体の許可リストに載っているもの。増やすときは
# docs/PYHIROBA_INTEGRATION.md と _ai.py のブラウザ経路の説明もそろえること。
ALLOWED_KINDS = {"ai-load", "ai-ask", "ai-models", "ai-ask-start", "ai-ask-next", "ai-probe"}


def test_only_allowed_kinds_are_used(fresh_ai, in_browser):
    run(fresh_ai.load())
    run(fresh_ai.ask("質問"))
    run(fresh_ai.models())
    run(fresh_ai.environment())
    run(fresh_ai.recommend())
    used = {kind for kind, _ in in_browser.calls}
    assert used <= ALLOWED_KINDS


def test_arguments_are_json_strings(fresh_ai, in_browser):
    """Pyodide と JS の境界は JSON 文字列だけに保つ。"""
    run(fresh_ai.load())
    run(fresh_ai.ask("質問"))
    for _kind, args in in_browser.calls:
        assert isinstance(args, str)
        json.loads(args)


@pytest.mark.parametrize("bad", [0, -1, -50, 1.5, "64", True, False])
def test_a_nonsense_length_is_refused_before_the_model_sees_it(fresh_ai, in_browser, bad):
    """透かすと、書いた本人に届かない形で外れる。

    Colab は transformers の奥から読めない例外を出し、ブラウザは黙って
    既定値に戻す。どちらも max_tokens=-50 と書いた理由には結び付かない。
    """
    with pytest.raises(ValueError, match="max_tokens"):
        run(fresh_ai.ask("質問", max_tokens=bad))
    assert in_browser.calls == [], "確かめる前に本体を呼んでいる"


@pytest.mark.parametrize("good", [None, 1, 64, 4096])
def test_ordinary_lengths_still_pass(fresh_ai, in_browser, good):
    run(fresh_ai.ask("質問", max_tokens=good))


def test_streaming_checks_the_length_too(fresh_ai, in_browser):
    async def gather():
        return [c async for c in fresh_ai.stream("質問", max_tokens=-1)]

    with pytest.raises(ValueError, match="max_tokens"):
        run(gather())


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


def test_colab_load_pins_the_model_revision(fresh_ai, fake_transformers):
    """配布元の版を固定して読むこと（S-1）。

    ``revision`` を渡さないと Hugging Face の main を追う。上流が更新された日から
    生徒の手元には**別の重み**が降ってきて、教材の答えだけが静かに変わる。
    """
    run(fresh_ai.load("qwen05"))
    assert fake_transformers["build"]["revision"] == _ai.MODELS["qwen05"]["colab_revision"]


def test_every_model_declares_a_pinned_revision():
    """一覧に足したモデルも、必ず版が固定されていること（S-1）。

    固定を忘れても普通に動いてしまうため、増やした時点でここが止める。
    """
    for name, entry in {**_ai.MODELS, **_ai.EMBED_MODELS}.items():
        revision = entry.get("colab_revision", "")
        assert re.fullmatch(r"[0-9a-f]{40}", revision), (
            f"{name} の colab_revision がコミット（40桁の16進）ではありません: {revision!r}"
        )


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


# --- 本体が壊れた応答を返したとき -------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("{not json", "読み取れませんでした"),
        ("", "読み取れませんでした"),
        ("[1,2,3]", "形が違います"),
        ("null", "形が違います"),
        ('"ok"', "形が違います"),
        ("123", "形が違います"),
    ],
)
def test_broken_host_replies_give_a_readable_error(fresh_ai, monkeypatch, raw, expected):
    """利用者に「'list' object has no attribute 'get'」を見せない。

    本体の実装はこれから書かれるので、開発中に必ず通る道になる。
    """
    async def broken_host(kind, args_json):
        return raw

    js = types.ModuleType("js")
    js.pyhirobaAsk = broken_host
    monkeypatch.setitem(sys.modules, "js", js)

    with pytest.raises(RuntimeError, match=expected):
        run(fresh_ai.load())


def test_text_that_is_not_a_string_does_not_crash(fresh_ai, in_browser):
    """本体が数値を返しても止まらない（文字列にして返す）。"""
    in_browser.replies["ai-ask"] = {"text": 123}
    assert run(fresh_ai.ask("q")) == "123"


# --- 少しずつ受け取る -------------------------------------------------------


def collect(chunks):
    """チャンクを順に流し込み、表示された文字を全部つなげる。"""
    f = _ai.ThinkingFilter()
    out = "".join(f.feed(c) for c in chunks)
    return out + f.finish()


@pytest.mark.parametrize(
    "chunks,expected",
    [
        (["答え", "は", "3です"], "答えは3です"),
        # <think> が丸ごと1チャンクに入る
        (["<think>考え</think>", "答え"], "答え"),
        # <think> がチャンクの境目で割れる（ここが取りこぼしやすい）
        (["<thi", "nk>考え</th", "ink>答え"], "答え"),
        (["<", "t", "h", "i", "n", "k", ">", "え", "</think>", "答"], "答"),
        # 閉じない think は最後まで見せない
        (["答え", "<think>まだ考え"], "答え"),
        (["<think>ずっと考えている"], ""),
        # think のあとにも本文が続く
        (["A", "<think>x</think>", "B", "<think>y</think>", "C"], "ABC"),
        ([], ""),
    ],
)
def test_streaming_hides_thinking_across_chunk_boundaries(chunks, expected):
    assert collect(chunks) == expected


def test_streaming_never_shows_a_half_written_tag():
    """<thi まで届いた時点で出してしまうと、あとから取り消せない。"""
    f = _ai.ThinkingFilter()
    assert f.feed("答え<thi") == "答え"  # 書きかけのタグだけ保留される
    assert f.feed("nk>秘密</think>") == ""  # think と分かったので何も出さない
    assert f.feed("です") == "です"
    assert f.finish() == ""


def test_ordinary_text_is_not_delayed():
    """タグの書きかけでない普通の文字は、待たせずにそのまま出す。"""
    f = _ai.ThinkingFilter()
    assert f.feed("こんにちは") == "こんにちは"
    assert f.feed("、元気？") == "、元気？"
    assert f.finish() == ""


def test_only_a_real_tag_prefix_is_held():
    f = _ai.ThinkingFilter()
    assert f.feed("答えは<") == "答えは"  # < は <think> の始まりかもしれない
    assert f.feed("3です") == "<3です"  # 違った。取り消さずに続けられる


def test_streaming_and_asking_agree(fresh_ai, in_browser):
    """つなげた結果が ask() と同じ文になること。"""
    in_browser.replies["ai-ask"] = {"text": "<think>考え</think>答えは3です"}

    async def gather():
        return "".join([c async for c in fresh_ai.stream("q")])

    assert run(gather()) == run(fresh_ai.ask("q")) == "答えは3です"


def test_stream_falls_back_when_the_host_cannot_do_it(fresh_ai, in_browser):
    """本体が少しずつ返せなくても、同じコードが動くこと（全文が一度に来る）。"""
    in_browser.replies["ai-ask"] = {"text": "全文です"}
    # ai-ask-start に id を返さない＝未対応

    async def gather():
        return [c async for c in fresh_ai.stream("q")]

    assert run(gather()) == ["全文です"]
    assert "ai-ask" in [kind for kind, _ in in_browser.calls]


def test_stream_skips_the_doomed_call_when_the_host_lists_its_features(fresh_ai, in_browser):
    """本体が機能を名乗るなら、失敗すると分かっている往復は省く（T2）。"""
    import js

    js.pyhirobaFeatures = "forms,ai,ai-probe"  # ai-stream が無い
    in_browser.replies["ai-ask"] = {"text": "全文です"}

    async def gather():
        return [c async for c in fresh_ai.stream("q")]

    assert run(gather()) == ["全文です"]
    kinds = [kind for kind, _ in in_browser.calls]
    assert "ai-ask-start" not in kinds, "名乗っていない機能を呼びに行かないこと"
    assert "ai-ask" in kinds


def test_stream_still_probes_a_host_that_names_nothing(fresh_ai, in_browser):
    """機能を名乗らない古い本体には、今までどおり聞いてみる（T2）。"""
    in_browser.replies["ai-ask"] = {"text": "全文です"}

    async def gather():
        return [c async for c in fresh_ai.stream("q")]

    run(gather())
    assert "ai-ask-start" in [kind for kind, _ in in_browser.calls]


def test_stream_uses_the_host_when_it_can(fresh_ai, monkeypatch):
    """ai-ask-start が id を返したら、ai-ask-next を繰り返す。"""
    parts = [
        {"text": "こん", "done": False},
        {"text": "にちは", "done": False},
        {"text": "！", "done": True},
    ]
    calls = []

    async def host(kind, args_json):
        calls.append(kind)
        if kind == "ai-load":
            return json.dumps({})
        if kind == "ai-ask-start":
            return json.dumps({"id": "s1"})
        return json.dumps(parts.pop(0))

    js = types.ModuleType("js")
    js.pyhirobaAsk = host
    monkeypatch.setitem(sys.modules, "js", js)

    async def gather():
        return [c async for c in fresh_ai.stream("q")]

    assert "".join(run(gather())) == "こんにちは！"
    assert calls.count("ai-ask-next") == 3
    assert "ai-ask" not in calls  # 全文取得には落ちていない


# --- Colab 経路で少しずつ受け取る -------------------------------------------


class _FakeStreamer:
    """transformers の TextIteratorStreamer の代役。

    本物と同じく「生成が進むまで待つ反復子」として振る舞う。
    """

    def __init__(self, tokenizer, **kwargs):
        self.pieces = []
        self.closed = False
        self.kwargs = kwargs

    def put(self, piece):
        self.pieces.append(piece)

    def end(self):
        self.closed = True

    def __iter__(self):
        while self.pieces or not self.closed:
            if self.pieces:
                yield self.pieces.pop(0)
            else:
                time.sleep(0.001)


def install_fake_streaming(monkeypatch, answer, fail=None):
    """一文字ずつ流す偽の pipeline と streamer を入れる。"""
    holder = {}

    def pipeline_call(prompt, streamer=None, **kwargs):
        holder["kwargs"] = kwargs
        if fail is not None:
            raise fail
        for ch in answer:
            streamer.put(ch)
        streamer.end()
        return [{"generated_text": answer}]

    pipeline_call.tokenizer = _FakeTokenizer()
    transformers = types.ModuleType("transformers")
    transformers.TextIteratorStreamer = _FakeStreamer
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    return pipeline_call, holder


def test_colab_streaming_yields_piece_by_piece(fresh_ai, monkeypatch):
    pipe, holder = install_fake_streaming(monkeypatch, "こんにちは")
    fresh_ai._pipe = pipe
    fresh_ai._name = "qwen05"

    async def gather():
        return [c async for c in fresh_ai.stream("q")]

    chunks = run(gather())
    assert "".join(chunks) == "こんにちは"
    assert len(chunks) > 1, "1回にまとめて返っていて、少しずつになっていない"
    assert holder["kwargs"]["max_new_tokens"] == 256


def test_colab_streaming_hides_thinking(fresh_ai, monkeypatch):
    pipe, _ = install_fake_streaming(monkeypatch, "<think>考え</think>答えは3です")
    fresh_ai._pipe = pipe
    fresh_ai._name = "qwen3_06"

    async def gather():
        return "".join([c async for c in fresh_ai.stream("q")])

    assert run(gather()) == "答えは3です"


def test_colab_streaming_reports_a_failure(fresh_ai, monkeypatch):
    """生成が別スレッドで落ちたとき、短い答えとして黙って返さないこと。"""
    pipe, _ = install_fake_streaming(monkeypatch, "", fail=RuntimeError("メモリが足りません"))
    fresh_ai._pipe = pipe
    fresh_ai._name = "qwen05"

    async def gather():
        return [c async for c in fresh_ai.stream("q")]

    with pytest.raises(RuntimeError, match="メモリが足りません"):
        run(gather())


def test_colab_streaming_falls_back_on_old_transformers(fresh_ai, monkeypatch):
    """TextIteratorStreamer が無い版でも、同じコードが動くこと。"""
    transformers = types.ModuleType("transformers")  # streamer なし
    monkeypatch.setitem(sys.modules, "transformers", transformers)

    def pipe(prompt, **kwargs):
        return [{"generated_text": "全文です"}]

    pipe.tokenizer = _FakeTokenizer()
    fresh_ai._pipe = pipe
    fresh_ai._name = "qwen05"

    async def gather():
        return [c async for c in fresh_ai.stream("q")]

    assert run(gather()) == ["全文です"]


def test_streaming_does_not_block_the_notebook(fresh_ai, monkeypatch):
    """待っているあいだ、ほかの処理が進めること（画面が固まらない）。"""
    pipe, _ = install_fake_streaming(monkeypatch, "あいうえお")
    fresh_ai._pipe = pipe
    fresh_ai._name = "qwen05"
    ticks = []

    async def heartbeat():
        for _ in range(20):
            await asyncio.sleep(0.002)
            ticks.append(1)

    async def both():
        beat = asyncio.ensure_future(heartbeat())
        chunks = [c async for c in fresh_ai.stream("q")]
        await beat
        return chunks

    run(both())
    assert ticks, "受け取っているあいだ、ほかの処理が一切進んでいない"


# --- 動く環境を調べる -------------------------------------------------------


def browser_env(**changes):
    """ブラウザで調べがついた状態。足りない項目は十分な値で埋める。"""
    found = {
        "known": True,
        "where": "browser",
        "webgpu": True,
        "memory_gb": 8,
        "ram_gb": None,
        "vram_gb": None,
        "cores": 8,
        "storage_mb": 60000,
        "label": "Chrome",
    }
    found.update(changes)
    return found


def colab_env(**changes):
    """Colab で調べがついた状態。"""
    found = {
        "known": True,
        "where": "colab",
        "webgpu": False,
        "memory_gb": None,
        "ram_gb": 12.7,
        "vram_gb": None,
        "cores": 8,
        "storage_mb": 60000,
        "label": "CPU",
    }
    found.update(changes)
    return found


@pytest.mark.parametrize(
    "found,expected",
    [
        # 調べられなかったら、環境によらず標準のものに落ちる
        ({"known": False}, "qwen05"),
        ({}, "qwen05"),
        # ブラウザ。WebGPU が無ければ WASM でも待てる 150M まで落とす
        (browser_env(), "qwen3_17"),
        (browser_env(webgpu=False), "llmjp150m"),
        # メモリ 4GB あれば、469MB しかない qwen35_08 が拾える
        (browser_env(memory_gb=4), "qwen35_08"),
        # 低スペック機。qwen05 より軽い qwen3_06 が拾えるので 150M まで落とさない
        (browser_env(memory_gb=2), "qwen3_06"),
        (browser_env(memory_gb=1), "llmjp150m"),
        # 回線ではなく置き場所が足りない場合も、落とす理由になる
        (browser_env(storage_mb=1000), "qwen35_08"),
        (browser_env(storage_mb=500), "llmjp150m"),
        # Colab。CPU だけなら 1.5B 以上は待てないので選ばない
        (colab_env(), "qwen35_08"),
        (colab_env(vram_gb=15.0), "qwen3_17"),
        (colab_env(vram_gb=2.0), "qwen35_08"),
        (colab_env(ram_gb=3.0), "llmjp150m"),
    ],
)
def test_the_best_model_that_actually_runs_is_chosen(found, expected):
    assert _ai.choose(found)[0] == expected


@pytest.mark.parametrize(
    "found",
    [
        browser_env(memory_gb=64, storage_mb=999999),
        colab_env(ram_gb=256.0, vram_gb=80.0),
        browser_env(),
        colab_env(),
    ],
)
def test_a_heavy_model_is_never_chosen_for_you(found):
    """``auto`` は ``auto=False`` のモデルを選ばないこと。

    ブラウザで 2.9GB を生徒一人ひとりが落とすかどうかは、教室の回線を知っている
    人が決めることで、機械が勝手に決めてよい話ではない。**どれだけ潤沢な環境でも
    選ばれない**ことを、環境を振って確かめる。
    """
    heavy = [n for n in _ai.MODELS if not _ai.auto_ok(n)]
    assert heavy, "auto を切ったモデルが無いと、この検査は何も守っていない"
    assert _ai.choose(found)[0] not in heavy


def test_a_heavy_model_is_still_listed_and_loadable_by_name():
    """おまかせでは選ばれないが、名前を書けば使えること（一覧にも残る）。"""
    heavy = next(n for n in _ai.MODELS if not _ai.auto_ok(n))
    assert heavy in _ai.MODELS
    assert _ai.resolve(heavy)[0] == heavy, "名前で指定しても解決できません"
    listed = [m["name"] for m in run(_ai.Ai().models())]
    assert heavy in listed, "ai.models() の一覧から消えています"


def test_the_reason_does_not_claim_the_top_when_something_heavier_exists():
    """「一覧でいちばん賢い」と言い切らないこと。

    auto から外したものが一覧には残っているので、言い切ると嘘になる。
    """
    _name, reason = _ai.choose(browser_env(memory_gb=64, storage_mb=999999))
    assert "一覧でいちばん賢い" not in reason


@pytest.mark.parametrize("found", [{"known": False}, browser_env(), colab_env()])
def test_every_choice_explains_itself(found):
    """理由の無いおすすめは出さない（利用者が判断を確かめられなくなる）。"""
    name, reason = _ai.choose(found)
    assert reason.endswith("。")
    assert _ai._short_label(name) in reason


def test_an_unmeasurable_browser_does_not_get_a_heavy_model():
    """Firefox と Safari には navigator.deviceMemory が無い。

    測れないぶんを「あるはず」で埋めると、動かない端末に 1.7B を薦めてしまう。
    分からないときは標準より上に行かない。
    """
    name, reason = _ai.choose(browser_env(memory_gb=None))
    assert name == _ai.DEFAULT_MODEL
    assert "分からなかった" in reason


def test_nothing_fits_still_returns_something_runnable():
    """条件を満たすものが無くても、名前と理由は返す（例外にしない）。"""
    name, reason = _ai.choose(browser_env(webgpu=False, memory_gb=1, storage_mb=10))
    assert name in _ai.MODELS
    assert "動かないかもしれません" in reason


@pytest.mark.parametrize("found", [browser_env(), colab_env(), {"known": False}])
def test_the_choice_can_always_be_loaded(found):
    """選ばれた名前が resolve() を通ること（読み込む直前で落ちない）。"""
    assert _ai.resolve(_ai.choose(found)[0])


# --- 環境を調べる（ブラウザ） -----------------------------------------------


def test_the_host_is_asked_with_an_empty_json_object(fresh_ai, in_browser):
    in_browser.replies["ai-probe"] = {"webgpu": True}
    run(fresh_ai.environment())
    kinds = dict(in_browser.calls)
    assert json.loads(kinds["ai-probe"]) == {}


def test_the_browser_reply_is_read(fresh_ai, in_browser):
    in_browser.replies["ai-probe"] = {
        "webgpu": True,
        "memoryGB": 8,
        "cores": 12,
        "storageMB": 40000,
        "browser": "Chrome 120",
    }
    found = run(fresh_ai.environment())
    assert found["known"] is True
    assert found["where"] == "browser"
    assert found["webgpu"] is True
    assert found["memory_gb"] == 8
    assert found["cores"] == 12
    assert found["storage_mb"] == 40000
    assert found["label"] == "Chrome 120"


def test_a_host_that_does_not_know_ai_probe_is_not_an_error(fresh_ai, in_browser):
    """未対応を伝えるために、本体が何かを実装する必要は無い（既定の {} で足りる）。"""
    found = run(fresh_ai.environment())  # FakeHost は知らない kind に {} を返す
    assert found["known"] is False
    assert run(fresh_ai.recommend()).name == _ai.DEFAULT_MODEL


def test_a_host_that_raises_is_not_an_error(fresh_ai, monkeypatch):
    async def refuse(kind, args_json):
        raise RuntimeError("許可されていない kind です")

    js = types.ModuleType("js")
    js.pyhirobaAsk = refuse
    monkeypatch.setitem(sys.modules, "js", js)
    assert run(fresh_ai.environment())["known"] is False


@pytest.mark.parametrize("junk", ["8", None, True, [], {}])
def test_values_that_are_not_numbers_are_treated_as_unknown(fresh_ai, in_browser, junk):
    """本体が文字列で返しても、比較で TypeError にならないこと。"""
    in_browser.replies["ai-probe"] = {"webgpu": True, "memoryGB": junk}
    found = run(fresh_ai.environment())
    assert found["memory_gb"] is None
    assert _ai.choose(found)[0] == _ai.DEFAULT_MODEL


def test_load_auto_uses_the_recommendation(fresh_ai, in_browser):
    in_browser.replies["ai-probe"] = {"webgpu": True, "memoryGB": 8, "storageMB": 60000}
    run(fresh_ai.load("auto"))
    sent = [json.loads(args) for kind, args in in_browser.calls if kind == "ai-load"]
    assert sent == [{"model": _ai.MODELS["qwen3_17"]["browser_key"]}]


def test_load_without_an_argument_still_ignores_the_environment(fresh_ai, in_browser):
    """既定を変えていないこと。同じ教材が環境ごとに違うモデルを読むと追えない。"""
    in_browser.replies["ai-probe"] = {"webgpu": True, "memoryGB": 8, "storageMB": 60000}
    run(fresh_ai.load())
    sent = [json.loads(args) for kind, args in in_browser.calls if kind == "ai-load"]
    assert sent == [{"model": _ai.MODELS[_ai.DEFAULT_MODEL]["browser_key"]}]
    assert "ai-probe" not in {kind for kind, _ in in_browser.calls}


# --- 環境を調べる（Colab） --------------------------------------------------


def install_fake_torch(monkeypatch, vram_bytes=None, name="Tesla T4"):
    """GPU のある／無い torch を差し替える。"""
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(
        is_available=lambda: vram_bytes is not None,
        get_device_properties=lambda index: types.SimpleNamespace(
            total_memory=vram_bytes, name=name
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.delitem(sys.modules, "js", raising=False)
    return torch


def test_a_gpu_runtime_is_recognised(fresh_ai, monkeypatch):
    install_fake_torch(monkeypatch, vram_bytes=15 * 1024**3)
    found = run(fresh_ai.environment())
    assert found["where"] == "colab"
    assert found["known"] is True
    assert found["vram_gb"] == 15.0
    assert found["label"] == "Tesla T4"


def test_a_cpu_runtime_is_recognised(fresh_ai, monkeypatch):
    install_fake_torch(monkeypatch, vram_bytes=None)
    found = run(fresh_ai.environment())
    assert found["vram_gb"] is None
    assert found["label"] == "CPU"
    # GPU が要るモデルは薦めない
    assert _ai.MODELS[_ai.choose(found)[0]]["needs"]["colab"]["vram_gb"] is None


def test_memory_is_read_without_extra_packages(monkeypatch):
    """psutil を足さずに /proc/meminfo から読めること。"""
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    assert _ai._total_ram_gb() > 0


def test_a_machine_without_proc_meminfo_does_not_crash(monkeypatch):
    """Windows などには /proc が無い。読めないだけで止まらないこと。"""

    def refuse(*args, **kwargs):
        raise FileNotFoundError("/proc/meminfo")

    monkeypatch.setattr("builtins.open", refuse)
    assert _ai._total_ram_gb() is None


def test_a_broken_torch_does_not_stop_the_check(fresh_ai, monkeypatch):
    """壊れた GPU 環境で、環境調べまで巻き添えにしない。"""
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(
        is_available=lambda: (_ for _ in ()).throw(RuntimeError("CUDA が壊れています"))
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.delitem(sys.modules, "js", raising=False)
    found = run(fresh_ai.environment())
    assert found["vram_gb"] is None
    assert _ai.choose(found)[0] in _ai.MODELS


def test_no_torch_yet_is_not_an_error(fresh_ai, monkeypatch):
    """まだ pip install していないだけ。入れ方の案内は load() の仕事。"""
    monkeypatch.setitem(sys.modules, "torch", None)  # import torch が失敗する
    monkeypatch.delitem(sys.modules, "js", raising=False)
    found = run(fresh_ai.environment())
    assert found["label"] == "CPU"


# --- おすすめの表示 ---------------------------------------------------------


def test_the_recommendation_shows_as_html(fresh_ai, monkeypatch):
    install_fake_torch(monkeypatch, vram_bytes=15 * 1024**3)
    found = run(fresh_ai.recommend())
    html = found._repr_html_()
    assert check_html(html) == []
    assert "Tesla T4" in html
    assert found.name in _ai.MODELS


def test_the_recommendation_is_readable_without_a_notebook(fresh_ai, monkeypatch):
    """PyHiroba では print() で確かめることもある。"""
    install_fake_torch(monkeypatch, vram_bytes=None)
    found = run(fresh_ai.recommend())
    assert found.name in repr(found)
    assert found.reason in repr(found)


def test_an_unknown_environment_still_renders():
    """調べがつかなくても表は作れること（ui.table は空だと例外になる）。"""
    shown = _ai.Recommendation("qwen05", "理由", {"known": False, "where": "colab"})
    assert check_html(shown._repr_html_()) == []


def test_the_recommendation_only_lists_what_was_measured():
    shown = _ai.Recommendation("qwen05", "理由", _ai._blank("browser"))
    labels = [row[0] for row in shown.rows()]
    assert "空き容量" not in labels
    assert "GPU のメモリ" not in labels
    assert "読み込む名前" in labels


# --- ai.talk（記憶つきの会話） ----------------------------------------------


class FakeModel:
    """Ai の代役。ask / stream だけを持ち、渡された prompt を控える。"""

    def __init__(self, replies=None, loaded=True):
        self.replies = list(replies or ["富士山です。"])
        self.prompts = []
        self.loaded = loaded

    def is_loaded(self):
        return self.loaded

    def _next(self, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]

    async def ask(self, prompt, max_tokens=None):
        return self._next(prompt)

    async def stream(self, prompt, max_tokens=None):
        for chunk in self._next(prompt):
            yield chunk


def make_talk(replies=None, loaded=True, **kwargs):
    model = FakeModel(replies, loaded=loaded)
    return _ai.Talk(model, **kwargs), model


def test_talk_carries_the_earlier_turns_into_the_next_prompt():
    """ai.ask() は1回分しか受け取らない。ここが埋めているのが記憶（T1）。"""
    talk, model = make_talk(["富士山です。", "3776メートルです。"])
    run(talk.ask("日本で一番高い山は？"))
    run(talk.ask("その高さは？"))
    second = model.prompts[1]
    assert "日本で一番高い山は？" in second
    assert "富士山です。" in second
    assert second.rstrip().endswith("AI:")  # 続きを書かせる形で終える


def test_talk_forgets_beyond_keep():
    """小さなモデルは長い文章が苦手。覚えておく往復を絞れること（T1）。"""
    talk, model = make_talk(["1つめ", "2つめ", "3つめ"], keep=1)
    run(talk.ask("A"))
    run(talk.ask("B"))
    run(talk.ask("C"))
    third = model.prompts[2]
    assert "B" in third and "2つめ" in third
    assert "1つめ" not in third  # 1往復ぶんより古いものは渡さない


def test_talk_cuts_off_what_the_model_wrote_for_us():
    """答えたあとに自分で会話を続けるモデルがある（T1）。"""
    talk, _ = make_talk(["富士山です。\nあなた: ありがとう\nAI: どういたしまして"])
    run(talk.ask("山は？"))
    assert talk.messages[-1] == {"role": "assistant", "content": "富士山です。"}


def test_talk_streams_a_growing_view_then_settles():
    """届いたぶんから見せ、最後に会話へ確定させる（T1）。"""
    talk, _ = make_talk(["こんにちは"])

    async def collect():
        return [view.messages async for view in talk.stream("やあ")]

    views = run(collect())
    assert len(views) == len("こんにちは") + 2  # 先に自分の発言 + 1文字ごと + 確定
    # 1つめは、まだ答えが来ていなくても自分の発言が見えていること
    assert views[0][0] == {"role": "user", "content": "やあ"}
    assert views[1][-1]["content"] == "こ"
    assert views[-1] == talk.messages
    # 書きかけは会話に残さない。残すと次の記憶が書きかけで埋まる
    assert talk.messages == [
        {"role": "user", "content": "やあ"},
        {"role": "assistant", "content": "こんにちは"},
    ]


def test_talk_renders_and_survives_the_sanitizer():
    talk, _ = make_talk()
    run(talk.ask("<script>alert(1)</script>"))
    html = talk._repr_html_()
    assert check_html(html) == []
    assert "<script" not in html.lower()


def test_talk_form_matches_its_own_field_name():
    """ui.form は欄の name をキーワード引数にする。ずれるとフォームだけ壊れる（T1）。

    利用者が名前を合わせなくてよいのが form() の値打ちなので、
    実際に submit() を通して確かめる。
    """
    talk, _ = make_talk(["どうも"])
    form = talk.form()
    assert [f.name for f in form.fields] == ["message"]

    async def collect():
        return [view async for view in form.submit(message="やあ")]

    run(collect())
    assert talk.messages == [
        {"role": "user", "content": "やあ"},
        {"role": "assistant", "content": "どうも"},
    ]


def test_talk_form_warns_only_where_it_really_cannot_work(monkeypatch):
    """注意書きは、フォームが動かない本体にだけ出す（T1）。

    in_browser() で判定すると PyHiroba では常に真になり、**フォームが動く本体
    にも警告が出る**。実際にそうなり、本体側が同梱を見送る事態になった。
    見るのは本体が名乗る機能一覧のほう。
    """
    talk, _ = make_talk()
    # Colab。js が無いので、そもそも注意書きは要らない
    assert "hui-alert" not in talk.form()._repr_html_()

    # フォームに対応していない古い PyHiroba
    monkeypatch.setattr(_ai, "in_browser", lambda: True)
    monkeypatch.setattr(_ai, "host_features", set)
    shown = talk.form()._repr_html_()
    assert "hui-alert-warning" in shown
    assert "talk.ask" in shown

    # 対応済みの PyHiroba。ここに注意書きを出してはいけない
    monkeypatch.setattr(_ai, "host_features", lambda: {"forms", "ai", "ai-probe"})
    assert "hui-alert" not in talk.form()._repr_html_()


def test_host_features_are_matched_whole(monkeypatch):
    """「,」区切りの完全一致で見る。部分一致だと ai-probe が ai を名乗る（T1）。"""
    js = types.ModuleType("js")
    js.pyhirobaFeatures = "forms, ai-probe"
    monkeypatch.setitem(sys.modules, "js", js)
    assert _ai.host_features() == {"forms", "ai-probe"}
    assert _ai.host_supports("forms")
    assert _ai.host_supports("ai-probe")
    assert not _ai.host_supports("ai")        # ai-probe の一部を拾わない
    assert not _ai.host_supports("form")      # forms の一部を拾わない


def test_host_features_is_empty_without_a_host(monkeypatch):
    """名乗らない古い本体と、js の無い Colab では空（T1）。"""
    js = types.ModuleType("js")  # pyhirobaFeatures を持たない古い本体
    monkeypatch.setitem(sys.modules, "js", js)
    assert _ai.host_features() == set()
    monkeypatch.setitem(sys.modules, "js", None)  # import すると ImportError
    assert _ai.host_features() == set()


def test_talk_validates_its_settings():
    with pytest.raises(ValueError, match="keep"):
        _ai.Talk(FakeModel(), keep=0)
    with pytest.raises(ValueError, match="max_tokens"):
        _ai.Talk(FakeModel(), max_tokens=0)


def test_talk_can_start_over():
    talk, _ = make_talk()
    run(talk.ask("やあ"))
    assert talk.clear().messages == []


def test_ai_talk_hands_back_a_talk_that_uses_it(fresh_ai):
    """ai.talk() が返すものが、その ai を使うこと（別のモデルを見に行かない）。"""
    talk = fresh_ai.talk(keep=2, names={"assistant": "先生"})
    assert isinstance(talk, _ai.Talk)
    assert talk._ai is fresh_ai
    assert talk.keep == 2
    assert talk.conversation.names == {"assistant": "先生"}


def test_talk_shows_what_you_typed_before_the_answer_arrives():
    """チャットなのだから、自分の発言は答えを待たずに見えること（T3）。

    ここを待ってから出すと、画面には「考え中」しか無い時間が続き、
    送れたのかどうかも分からない。
    """
    talk, _ = make_talk(["こんにちは"])

    async def first():
        async for view in talk.stream("やあ"):
            return view

    view = run(first())
    shown = view._repr_html_()
    assert "やあ" in shown                      # 打った内容が出ている
    assert "hui-msg hui-msg-user" in shown
    assert "hui-thinking" in shown              # AI の側は考え中の点
    assert check_html(shown) == []


def test_talk_says_when_it_is_still_loading_the_model():
    """読み込みと生成を言い分ける。初回は数分かかる（T3）。"""
    loading, _ = make_talk(["答え"], loaded=False)

    async def first(talk):
        async for view in talk.stream("やあ"):
            return view

    assert "モデルを読み込んでいます" in run(first(loading))._repr_html_()
    ready, _ = make_talk(["答え"], loaded=True)
    assert "モデルを読み込んでいます" not in run(first(ready))._repr_html_()


def test_talk_says_so_when_nothing_came_back():
    """空の吹き出しは故障に見える。返らなかったことを言葉にする（T3）。"""
    talk, _ = make_talk([""])

    async def drain():
        return [v async for v in talk.stream("やあ")]

    run(drain())
    assert talk.messages[-1]["content"] == _ai.Talk.NO_ANSWER

    asked, _ = make_talk([""])
    run(asked.ask("やあ"))
    assert asked.messages[-1]["content"] == _ai.Talk.NO_ANSWER


def test_is_loaded_reports_the_right_thing_per_environment(fresh_ai, monkeypatch):
    """待ち方を変える判断材料。経路ごとに見る場所が違う（T3）。"""
    assert not fresh_ai.is_loaded()
    fresh_ai._pipe = object()
    assert fresh_ai.is_loaded()

    monkeypatch.setattr(_ai, "in_browser", lambda: True)
    fresh_ai._pipe = object()      # ブラウザでは _pipe を使わない
    fresh_ai._name = None
    assert not fresh_ai.is_loaded()
    fresh_ai._name = "qwen05-q8"
    assert fresh_ai.is_loaded()


# --- 生成が止まったときの逃げ道 ---------------------------------------------


def install_streaming_transformers(monkeypatch, produce):
    """TextIteratorStreamer つきの代役。``produce(streamer)`` が生成側の中身。"""
    import queue

    class TextIteratorStreamer:
        def __init__(self, tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=None):
            self.timeout = timeout
            self._queue: queue.Queue = queue.Queue()

        def __iter__(self):
            return self

        def __next__(self):
            value = self._queue.get(timeout=self.timeout)
            if value is None:
                raise StopIteration
            return value

        def put(self, text):
            self._queue.put(text)

        def end(self):
            self._queue.put(None)

    recorded = install_fake_transformers(monkeypatch)
    sys.modules["transformers"].TextIteratorStreamer = TextIteratorStreamer

    def run_pipe(messages, streamer=None, **kwargs):
        produce(streamer)
        return [{"generated_text": [{"role": "assistant", "content": ""}]}]

    def pipeline(*a, **k):
        holder = run_pipe
        holder.tokenizer = object()
        return holder

    monkeypatch.setattr(sys.modules["transformers"], "pipeline", pipeline)
    return recorded


def test_a_generation_that_goes_quiet_gives_up_instead_of_waiting_forever(
    fresh_ai, monkeypatch
):
    """timeout を渡さないと next() は永久に待ち、考え中から抜けられない（S3）。

    Colab で実際にそうなった。上限を切って、待ち続けずに理由を言う。
    """
    install_streaming_transformers(monkeypatch, produce=lambda streamer: None)  # 何も出さない
    monkeypatch.setattr(_ai, "STREAM_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(_ai, "STREAM_POLL_SECONDS", 0.05)
    run(fresh_ai.load("llmjp150m"))

    async def drain():
        return [c async for c in fresh_ai.stream("やあ")]

    # 上限が抜けると本当に永久に待つので、テスト自体を止まらせない形で確かめる
    # （そのまま pytest.raises で囲むと、退行したとき失敗ではなく停止になる）
    outcome = {}

    def attempt():
        try:
            run(drain())
        except BaseException as error:  # noqa: BLE001 — 呼び出し側へ運ぶ
            outcome["error"] = error

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(timeout=20)
    assert not worker.is_alive(), "上限が切られておらず、いつまでも待ち続けています"
    assert isinstance(outcome.get("error"), TimeoutError), outcome
    assert "何も返しませんでした" in str(outcome["error"])


def test_the_streamer_is_given_a_deadline(fresh_ai, monkeypatch):
    """上限そのものが渡っていること（渡し忘れると永久待ちに戻る）（S3）。"""
    seen = {}

    def produce(streamer):
        seen["timeout"] = streamer.timeout
        streamer.put("答え")
        streamer.end()

    install_streaming_transformers(monkeypatch, produce)
    run(fresh_ai.load("llmjp150m"))

    async def drain():
        return [c async for c in fresh_ai.stream("やあ")]

    assert run(drain()) == ["答え"]
    # 1回の待ちは区切った長さ。通算の上限は呼び出し側が数える
    assert seen["timeout"] == _ai.STREAM_POLL_SECONDS


def test_two_generations_at_once_are_refused(fresh_ai, monkeypatch):
    """pipeline はスレッド安全ではない。同時に走らせると両方壊れる（S3）。

    フォームの送信中にノートブックのセルからもう1回聞くと、実際に起きる。
    """
    install_streaming_transformers(monkeypatch, produce=lambda s: (s.put("答え"), s.end()))
    run(fresh_ai.load("llmjp150m"))
    fresh_ai._generating.acquire()  # 1本目が走っている状態

    async def drain():
        return [c async for c in fresh_ai.stream("やあ")]

    with pytest.raises(RuntimeError, match="前の生成がまだ終わっていません"):
        run(drain())
    fresh_ai._generating.release()
    assert run(drain()) == ["答え"]  # 終われば次は通る


def test_the_lock_is_released_even_when_generation_fails(fresh_ai, monkeypatch):
    """落ちたまま鍵を持ち続けると、以後ずっと聞けなくなる（S3）。"""

    def explode(streamer):
        raise RuntimeError("生成が落ちた")

    install_streaming_transformers(monkeypatch, explode)
    run(fresh_ai.load("llmjp150m"))

    async def drain():
        return [c async for c in fresh_ai.stream("やあ")]

    with pytest.raises(RuntimeError, match="生成が落ちた"):
        run(drain())
    assert not fresh_ai._generating.locked(), "落ちたあとも鍵を持ったままです"


def test_waiting_shows_how_long_it_has_been():
    """動かない「考え中」は故障と見分けが付かない（S3）。"""
    talk, _ = make_talk()
    assert "秒" not in talk._waiting(0.0)._repr_html_()
    assert "12秒" in talk._waiting(12.3)._repr_html_()
    loading, _ = make_talk(loaded=False)
    assert "モデルを読み込んでいます" in loading._waiting(5.0)._repr_html_()
    assert "5秒" in loading._waiting(5.0)._repr_html_()


# --- 埋め込み（ai.embed / ai.search） ---------------------------------------


def fake_embed_host(monkeypatch, dim=4, features="forms,ai,ai-probe,ai-embed"):
    """本体の ai-embed の代役。渡された texts を記録し、正規化済みを返す。

    次元は本物（384）だとテストが重くなるので小さくし、宣言側も揃えておく
    （揃えないと、こちらが入れた「次元が変わったら止める」検査に引っかかる）。
    """
    monkeypatch.setitem(_ai.EMBED_MODELS["minilm"], "dim", dim)
    sent = []

    def unit(seed, size):
        raw = [((seed * 7 + i * 13) % 11) + 1 for i in range(size)]
        length = sum(v * v for v in raw) ** 0.5
        return [v / length for v in raw]

    async def ask(kind, args_json):
        args = json.loads(args_json)
        if kind != "ai-embed":
            return json.dumps({})
        sent.append(args)
        texts = args["texts"]
        return json.dumps(
            {"vectors": [unit(len(t), dim) for t in texts], "dim": dim, "model": args["model"]}
        )

    js = types.ModuleType("js")
    js.pyhirobaAsk = ask
    if features is not None:
        js.pyhirobaFeatures = features
    monkeypatch.setitem(sys.modules, "js", js)
    return sent


def test_embedding_models_are_kept_out_of_the_chat_list():
    """同じ辞書に入れると ai.models() / load() / recommend() が壊れる（E1）。"""
    assert not set(_ai.EMBED_MODELS) & set(_ai.MODELS)
    # ai.load() は埋め込みモデルを受け付けない
    with pytest.raises(ValueError, match="選べません"):
        _ai.resolve("minilm")
    # おすすめの判断材料（rank）を持たない＝recommend() の対象にならない
    for spec in _ai.EMBED_MODELS.values():
        assert "rank" not in spec and "needs" not in spec


def test_the_model_list_only_shows_models_you_can_load(fresh_ai, fake_transformers):
    """ai.models() に、生成できないモデルを混ぜない（E1）。"""
    listed = {entry["name"] for entry in run(fresh_ai.models())}
    assert listed == set(_ai.MODELS)
    assert not listed & set(_ai.EMBED_MODELS)


@pytest.mark.parametrize("name", sorted(_ai.EMBED_MODELS))
def test_both_paths_use_the_same_embedding_model(name):
    """環境で違うモデルが動くと、同じ文のベクトルが別物になる（E1）。"""
    spec = _ai.EMBED_MODELS[name]
    assert _bare_model_name(spec["colab_id"]) == _bare_model_name(spec["browser_repo"])
    assert "/" in spec["colab_id"] and "/" in spec["browser_repo"]
    assert isinstance(spec["dim"], int)


def test_unknown_embedding_model_is_rejected():
    assert _ai.resolve_embed(None) == _ai.DEFAULT_EMBED_MODEL
    assert _ai.resolve_embed("minilm") == "minilm"
    with pytest.raises(ValueError, match="選べません"):
        _ai.resolve_embed("qwen05")  # チャット用は通さない


def test_embed_returns_one_vector_for_a_string(fresh_ai, monkeypatch):
    """str なら1本、リストなら同じ順で返す（E2）。"""
    fake_embed_host(monkeypatch)
    one = run(fresh_ai.embed("怖い本"))
    assert isinstance(one, list) and isinstance(one[0], float)

    many = run(fresh_ai.embed(["怖い本", "料理の本"]))
    assert len(many) == 2 and isinstance(many[0], list)
    # 1件のリストは、入れ子のまま返す（str とは形が違う）
    assert isinstance(run(fresh_ai.embed(["怖い本"]))[0], list)


def test_embed_of_nothing_is_nothing(fresh_ai, monkeypatch):
    sent = fake_embed_host(monkeypatch)
    assert run(fresh_ai.embed([])) == []
    assert sent == [], "空なら本体を呼ばない"


def test_embed_splits_large_batches_so_both_environments_agree(fresh_ai, monkeypatch):
    """本体は 257 件以上を断る。素通しすると Colab とだけ結果が変わる（E2）。"""
    sent = fake_embed_host(monkeypatch)
    texts = [f"本{i}" for i in range(600)]
    vectors = run(fresh_ai.embed(texts))
    assert len(vectors) == 600
    assert [len(call["texts"]) for call in sent] == [256, 256, 88]
    # 分けても順番は保つ
    assert sum(len(call["texts"]) for call in sent) == 600


def test_embed_says_so_on_a_host_without_the_feature(fresh_ai, monkeypatch):
    """版ではなく目印で判定する。目印が無ければ理由の分かるエラー（E2）。"""
    fake_embed_host(monkeypatch, features="forms,ai,ai-probe")
    with pytest.raises(RuntimeError, match="まだ文のベクトル化に対応していません"):
        run(fresh_ai.embed("やあ"))


def test_embed_sends_the_agreed_shape(fresh_ai, monkeypatch):
    """本体と凍結した契約どおりの JSON を投げること（E2）。"""
    sent = fake_embed_host(monkeypatch)
    run(fresh_ai.embed(["あ", "い"], model="minilm"))
    assert sent == [{"model": "minilm", "texts": ["あ", "い"]}]


def test_a_host_that_returns_unnormalized_vectors_is_caught(fresh_ai, monkeypatch):
    """正規化されていないと内積がコサインにならず、近い順が静かに狂う（E2）。"""

    monkeypatch.setitem(_ai.EMBED_MODELS["minilm"], "dim", 2)  # 長さは正しい状態にする

    async def ask(kind, args_json):
        texts = json.loads(args_json)["texts"]
        return json.dumps({"vectors": [[3.0, 4.0] for _ in texts], "dim": 2})

    js = types.ModuleType("js")
    js.pyhirobaAsk = ask
    js.pyhirobaFeatures = "ai-embed"
    monkeypatch.setitem(sys.modules, "js", js)
    with pytest.raises(RuntimeError, match="正規化されていません"):
        run(fresh_ai.embed("やあ"))


def test_a_host_that_returns_the_wrong_count_is_caught(fresh_ai, monkeypatch):
    async def ask(kind, args_json):
        return json.dumps({"vectors": [[1.0]], "dim": 1})

    js = types.ModuleType("js")
    js.pyhirobaAsk = ask
    js.pyhirobaFeatures = "ai-embed"
    monkeypatch.setitem(sys.modules, "js", js)
    with pytest.raises(RuntimeError, match="ベクトルの数が合いません"):
        run(fresh_ai.embed(["あ", "い"]))


def test_a_refusal_from_the_host_is_readable(fresh_ai, monkeypatch):
    """本体が断った理由（日本語）が、そのまま読める形で出ること（E2）。"""

    async def ask(kind, args_json):
        raise RuntimeError("一度に渡せるのは256件までです。分割してください")

    js = types.ModuleType("js")
    js.pyhirobaAsk = ask
    js.pyhirobaFeatures = "ai-embed"
    monkeypatch.setitem(sys.modules, "js", js)
    with pytest.raises(RuntimeError, match="一度に渡せるのは256件までです"):
        run(fresh_ai.embed("やあ"))


def test_search_ranks_by_meaning(fresh_ai, monkeypatch):
    """近い順に並べ、index と text を添えて返す（E3）。"""
    monkeypatch.setattr(
        _ai.Ai, "embed", lambda self, texts, model=None: _canned(texts)
    )
    hits = run(fresh_ai.search("怖い本", ["料理", "怪談", "宇宙"]))
    assert [hit["index"] for hit in hits] == [1, 0, 2]
    assert hits[0]["text"] == "怪談"
    assert hits[0]["score"] > hits[-1]["score"]


async def _canned(texts):
    """query が「怪談」にいちばん近い、という決め打ちのベクトル。"""
    table = {"怖い本": [1.0, 0.0], "怪談": [0.96, 0.28], "料理": [0.6, 0.8], "宇宙": [0.0, 1.0]}
    return [table[text] for text in texts]


def test_search_top_k_and_validation(fresh_ai, monkeypatch):
    monkeypatch.setattr(_ai.Ai, "embed", lambda self, texts, model=None: _canned(texts))
    assert len(run(fresh_ai.search("怖い本", ["料理", "怪談", "宇宙"], top_k=2))) == 2
    assert run(fresh_ai.search("怖い本", [])) == []
    for bad in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="top_k"):
            run(fresh_ai.search("怖い本", ["料理"], top_k=bad))


def test_search_asks_the_host_only_once(fresh_ai, monkeypatch):
    """質問と文書を別々に投げると往復が2回になる（E3）。"""
    sent = fake_embed_host(monkeypatch)
    run(fresh_ai.search("怖い本", ["料理", "怪談"]))
    assert len(sent) == 1
    assert sent[0]["texts"] == ["怖い本", "料理", "怪談"]


def test_colab_pooling_ignores_padding_and_normalizes(fresh_ai, monkeypatch):
    """Colab 側の平均プーリングを実数値で確かめる（E4）。

    短い文には padding が付く。これを平均に混ぜると、文の長さでベクトルが
    変わってしまい、検索の順位が狂う。**混ざっていないこと**を数で見る。
    """
    torch = require_torch()

    # 1文目は2語＋padding、2文目は3語。padding には極端な値を入れてあるので、
    # 混ざっていれば結果が大きくずれる
    hidden = torch.tensor(
        [
            [[1.0, 0.0], [3.0, 0.0], [999.0, 999.0]],
            [[0.0, 1.0], [0.0, 3.0], [0.0, 2.0]],
        ]
    )
    mask = torch.tensor([[1, 1, 0], [1, 1, 1]])

    class FakeModel:
        def eval(self):
            return self

        def __call__(self, **_):
            return types.SimpleNamespace(last_hidden_state=hidden)

    def tokenizer(texts, **_):
        return {"input_ids": torch.zeros_like(mask), "attention_mask": mask}

    fake = types.ModuleType("transformers")
    fake.AutoModel = types.SimpleNamespace(from_pretrained=pinned(lambda repo, revision: FakeModel()))
    fake.AutoTokenizer = types.SimpleNamespace(from_pretrained=pinned(lambda repo, revision: tokenizer))
    monkeypatch.setitem(sys.modules, "transformers", fake)
    monkeypatch.delitem(sys.modules, "js", raising=False)

    got = fresh_ai._embed_with_transformers(["みじかい文", "すこし長い文"], "minilm")

    # padding を除いた平均は [2,0] と [0,2]。正規化すると [1,0] と [0,1]
    assert got[0] == pytest.approx([1.0, 0.0], abs=1e-6)
    assert got[1] == pytest.approx([0.0, 1.0], abs=1e-6)
    # 長さが 1（＝内積がそのままコサイン類似度になる）
    for vector in got:
        assert sum(v * v for v in vector) ** 0.5 == pytest.approx(1.0, abs=1e-6)


def test_the_embedder_is_loaded_once_and_is_not_the_chat_model(fresh_ai, monkeypatch):
    """埋め込みは生成とは別のモデル。load() の状態と混ざらないこと（E4）。"""
    require_torch()
    built = []

    class FakeModel:
        def eval(self):
            return self

    fake = types.ModuleType("transformers")
    fake.AutoModel = types.SimpleNamespace(
        from_pretrained=pinned(lambda repo, revision: built.append((repo, revision)) or FakeModel())
    )
    fake.AutoTokenizer = types.SimpleNamespace(from_pretrained=pinned(lambda repo, revision: object()))
    monkeypatch.setitem(sys.modules, "transformers", fake)

    fresh_ai._load_embedder("minilm")
    fresh_ai._load_embedder("minilm")
    entry = _ai.EMBED_MODELS["minilm"]
    assert built == [(entry["colab_id"], entry["colab_revision"])], "2回目は読み直さない"
    # 生成側は手つかず＝ai.load() と互いに影響しない
    assert fresh_ai._pipe is None and fresh_ai._name is None
    assert not fresh_ai.is_loaded()


def test_a_change_of_model_upstream_is_caught(fresh_ai, monkeypatch):
    """本体は配布元を版で固定していない。差し替わると黙って別物が返る（E5）。"""

    async def ask(kind, args_json):
        texts = json.loads(args_json)["texts"]
        # 384 のはずが 3 次元＝別のモデルに差し替わった状態
        return json.dumps({"vectors": [[0.6, 0.8, 0.0] for _ in texts], "dim": 3})

    js = types.ModuleType("js")
    js.pyhirobaAsk = ask
    js.pyhirobaFeatures = "ai-embed"
    monkeypatch.setitem(sys.modules, "js", js)
    with pytest.raises(RuntimeError, match="本目のベクトルの長さ"):
        run(fresh_ai.embed("やあ"))


# --- 監査で見つかった「黙って間違う」書き方 -----------------------------------


def test_a_string_of_documents_is_refused_not_split(fresh_ai, monkeypatch):
    """文字列を渡すと1文字ずつ別の文になる。例外にならないのが危ない（E6）。"""
    fake_embed_host(monkeypatch)
    with pytest.raises(ValueError, match="1文字ずつ"):
        run(fresh_ai.search("怖い本", "あいうえお"))
    # embed(str) は「1文だけ」の正規の書き方なので、こちらは通す
    assert isinstance(run(fresh_ai.embed("あいう"))[0], float)


def test_a_dict_of_documents_is_refused_not_keyed(fresh_ai, monkeypatch):
    """辞書を渡すとキーだけが使われ、説明文が消える（E6）。

    蔵書検索でいちばん起きやすい書き間違い。
    """
    fake_embed_host(monkeypatch)
    with pytest.raises(ValueError, match="キーだけが使われて"):
        run(fresh_ai.search("怖い本", {"真夜中の校舎": "深夜の学校に…"}))
    with pytest.raises(ValueError, match="キーだけが使われて"):
        run(fresh_ai.embed({"題名": "説明"}))


def test_something_that_is_not_a_list_says_so(fresh_ai, monkeypatch):
    """'int' object is not iterable では、何が悪いのか分からない（E6）。"""
    fake_embed_host(monkeypatch)
    for bad in (123, None, 1.5):
        with pytest.raises(ValueError, match="文のリストを渡してください"):
            run(fresh_ai.embed(bad))


def test_too_many_texts_are_refused_before_the_browser_freezes(fresh_ai, monkeypatch):
    """際限なく受けると、ブラウザが何分も固まったまま落ちる（E6）。"""
    fake_embed_host(monkeypatch)
    with pytest.raises(ValueError, match="10000 件まで"):
        run(fresh_ai.embed([f"x{i}" for i in range(_ai.EMBED_LIMIT + 1)]))


def test_vectors_of_different_lengths_are_all_checked(fresh_ai, monkeypatch):
    """1本目だけ見ていると、途中から混じった別物を素通しする（E6）。

    dot() が zip で切りそろえるため、そのままだと近い順だけが静かに狂う。
    """
    monkeypatch.setitem(_ai.EMBED_MODELS["minilm"], "dim", 3)

    async def ask(kind, args_json):
        # 1本目は正しく、2本目だけ長さが違う
        return json.dumps({"vectors": [[1.0, 0.0, 0.0], [1.0, 0.0]], "dim": 3})

    js = types.ModuleType("js")
    js.pyhirobaAsk = ask
    js.pyhirobaFeatures = "ai-embed"
    monkeypatch.setitem(sys.modules, "js", js)
    with pytest.raises(RuntimeError, match="2本目のベクトルの長さ"):
        run(fresh_ai.embed(["あ", "い"]))


def test_comparing_different_lengths_is_refused():
    """zip は黙って短いほうに切る。近さだけが静かに狂うので止める（E6）。"""
    assert _ai.dot([1.0, 0.0], [1.0, 0.0]) == 1.0
    with pytest.raises(ValueError, match="長さの違うベクトル"):
        _ai.dot([1.0, 0.0, 0.0], [1.0, 0.0])


def test_a_broken_vector_says_it_is_the_host(fresh_ai, monkeypatch):
    """'could not convert string to float' では本体の不具合と分からない（E6）。"""
    for broken in ([["文字列"]], [[None, None]], [42]):

        async def ask(kind, args_json, broken=broken):
            return json.dumps({"vectors": broken, "dim": 384})

        js = types.ModuleType("js")
        js.pyhirobaAsk = ask
        js.pyhirobaFeatures = "ai-embed"
        monkeypatch.setitem(sys.modules, "js", js)
        with pytest.raises(RuntimeError, match="数でないものが混じっています"):
            run(fresh_ai.embed("やあ"))


def test_the_embedder_loads_once_even_from_two_threads(fresh_ai, monkeypatch):
    """フォームの別スレッドとセルがかち合っても、二重に読まない（E6）。"""
    require_torch()
    built = []
    ready = threading.Barrier(2)

    def slow_load(repo, *, revision):
        ready.wait(timeout=5)  # 2つを確実に同時にぶつける
        built.append(repo)
        return types.SimpleNamespace(eval=lambda: None)

    fake = types.ModuleType("transformers")
    fake.AutoModel = types.SimpleNamespace(from_pretrained=slow_load)
    fake.AutoTokenizer = types.SimpleNamespace(from_pretrained=pinned(lambda repo, revision: object()))
    monkeypatch.setitem(sys.modules, "transformers", fake)

    # 鍵が無いと両方が読み込みに入り、Barrier が揃って built が 2 件になる。
    # 鍵があると片方が待つので Barrier は揃わず、timeout で BrokenBarrier になる
    workers = [threading.Thread(target=lambda: _try(fresh_ai)) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
    assert len(built) <= 1, f"モデルを {len(built)} 回読んでいます（鍵が効いていない）"


def _try(ai_object):
    try:
        ai_object._load_embedder("minilm")
    except Exception:  # noqa: BLE001 — Barrier の timeout は想定内
        pass


def test_embedding_does_not_wait_for_a_running_generation(fresh_ai, monkeypatch):
    """生成中でも embed の読み込みは待たされないこと（E6）。

    鍵を共用にすると、生成が終わるまで _load_embedder が返らない。embed() は
    イベントループの上から呼ばれるので、そこで止まるとノートブックごと固まる。
    **実際に生成中の状態を作って、読み込みが返ってくるかで確かめる。**
    """
    fake = types.ModuleType("transformers")
    fake.AutoModel = types.SimpleNamespace(
        from_pretrained=pinned(lambda repo, revision: types.SimpleNamespace(eval=lambda: None))
    )
    fake.AutoTokenizer = types.SimpleNamespace(from_pretrained=pinned(lambda repo, revision: object()))
    monkeypatch.setitem(sys.modules, "transformers", fake)

    fresh_ai._generating.acquire()  # 生成が走っている状態にする
    try:
        done = threading.Event()
        worker = threading.Thread(
            target=lambda: (fresh_ai._load_embedder("minilm"), done.set()), daemon=True
        )
        worker.start()
        assert done.wait(timeout=3), "生成の鍵に引きずられて、読み込みが返ってきません"
    finally:
        fresh_ai._generating.release()
