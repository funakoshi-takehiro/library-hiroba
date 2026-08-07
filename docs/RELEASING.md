# リリース手順（PyPI 公開）

ui-hiroba は GitHub Actions + **PyPI Trusted Publishing** で公開します。
API トークンの発行・保管は不要です（GitHub Actions の OIDC で認証されます）。
費用はかかりません（PyPI・GitHub Actions とも public リポジトリは無料）。

## 一回だけの準備（手動・約5分）

1. [pypi.org](https://pypi.org/) のアカウントを作成（未作成の場合）
2. ログイン後、[Publishing の設定ページ](https://pypi.org/manage/account/publishing/) を開く
3. **「Add a new pending publisher」** に以下を入力して登録:

   | 項目 | 値 |
   |---|---|
   | PyPI Project Name | `ui-hiroba` |
   | Owner | `funakoshi-takehiro` |
   | Repository name | `ui-hiroba` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. GitHub リポジトリ側で environment を作成:
   Settings → Environments → **New environment** → 名前 `pypi` → Save
   （保護ルールは任意。タグ push できるのは自分だけなので必須ではありません）

## 毎回のリリース手順

1. `src/ui_hiroba/__init__.py` の `__version__` を上げる（例: `0.1.0` → `0.1.1`）
2. main にマージ後、バージョンタグを打って push:

   ```bash
   git tag v0.1.1
   git push origin v0.1.1
   ```

3. GitHub Actions の `Release to PyPI` ワークフローが自動で
   ビルド（sdist + py3-none-any wheel）→ PyPI 公開まで行います
4. 数分後に確認:
   - https://pypi.org/project/ui-hiroba/
   - Colab で `%pip install ui-hiroba` → `import ui_hiroba`

## 補足

- **micropip（PyHiroba / Pyodide）対応**: 本パッケージは純 Python・依存ゼロなので、
  ビルドされる wheel は `py3-none-any`。micropip はこれを PyPI からそのまま
  インストールできます（通信許可は pypi.org / files.pythonhosted.org）。
- 初回リリース（`v0.1.0`）が成功すると pending publisher は通常の publisher に昇格し、
  以後は同じ手順の 1〜3 だけで公開できます。
