"""全部品が満たすべき不変条件。

- 出力が PyHiroba のサニタイザで変化しない（禁止タグ・イベント属性・
  javascript: URL・id 属性を含まず、タグの開閉が正しい）
- ユーザーが渡したテキストは必ずエスケープされる
"""

from __future__ import annotations

import pytest
from conftest import sample_widgets
from sanitize_check import check_html

import ui_hiroba as ui

# XSS でよく使われるパターンを text 引数に注入する
EVIL = '<script>alert(1)</script><img src=x onerror=alert(1)>"><iframe src="javascript:alert(1)"></iframe>'


@pytest.mark.parametrize("name", sorted(sample_widgets()))
def test_clean_output_passes_sanitize_check(name):
    widget = sample_widgets()[name]
    assert check_html(widget._repr_html_()) == []


@pytest.mark.parametrize("name", sorted(sample_widgets()))
def test_evil_text_is_escaped(name):
    widget = sample_widgets(EVIL)[name]
    rendered = widget._repr_html_()
    assert check_html(rendered) == []
    assert "<script" not in rendered.lower()
    # 注入したタグは文字列として（エスケープされて）表示される
    assert "&lt;script&gt;" in rendered


@pytest.mark.parametrize("name", sorted(sample_widgets()))
def test_style_and_root_are_present(name):
    rendered = sample_widgets()[name]._repr_html_()
    assert rendered.startswith("<style>")
    assert '<div class="hui">' in rendered
    # 既定はライト、ダークは data-theme="dark" のときだけ
    assert '[data-theme="dark"] .hui' in rendered
    # OS の配色設定は見ない（ライトのページで部品だけ黒くなるのを防ぐ）
    assert "prefers-color-scheme" not in rendered


def test_raw_html_is_not_escaped():
    rendered = ui.html("<b>太字</b>")._repr_html_()
    assert "<b>太字</b>" in rendered
    assert check_html(rendered) == []


def test_raw_html_with_css_passes_sanitize_check():
    rendered = ui.html(
        '<div class="fukidashi">やあ</div>',
        css=".fukidashi { border: 2px solid pink; }",
    )._repr_html_()
    assert check_html(rendered) == []


def test_css_cannot_break_out_of_style_block():
    # CSS 内の </style> で <style> を早期終了させてタグを注入する攻撃の無害化。
    # 無害化後、注入された "<script>" は style 要素内の不活性なテキストのままになる。
    rendered = ui.html("safe", css="</style><script>alert(1)</script>")._repr_html_()
    assert rendered.count("</style>") == 1  # 早期終了させる </style> は残っていない
    assert check_html(rendered) == []  # パース上 script タグは存在しない


def test_no_javascript_anywhere():
    for widget in sample_widgets().values():
        rendered = widget._repr_html_().lower()
        assert "<script" not in rendered
        assert "javascript:" not in rendered
        assert "onclick" not in rendered
