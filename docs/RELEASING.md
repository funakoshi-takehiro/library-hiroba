# 公開手順（PyPI へのリリース）

このドキュメントどおりに進めると、Colab で `pip install ui-hiroba` が通るようになります。
**費用は一切かかりません**（PyPI も GitHub Actions の公開リポジトリ枠も無料）。

パスワードや API トークンをリポジトリに置く必要もありません。GitHub Actions と PyPI が
直接信頼関係を結ぶ **Trusted Publishing（信頼された公開元）** という仕組みを使います。

---

## 全体の流れ

```
【最初の1回だけ】                        【リリースのたび】

  1. PyPI アカウントを作る                 A. バージョン番号を上げる
  2. PyPI に「公開元」を登録する     ──▶   B. タグを打って push する
  3. GitHub に環境 pypi を作る             C. 自動で公開される（数分待つだけ）
```

準備は **1回だけ・15分ほど**。2回目以降は「タグを打つ」だけです。

---

# 最初の1回だけ行う準備

## 手順1: PyPI のアカウントを作る

1. https://pypi.org/account/register/ を開く
2. メールアドレス・ユーザー名・パスワードを登録する
3. 届いたメールのリンクを開いて、メールアドレスを確認する
4. **二要素認証（2FA）を設定する** — PyPI では必須です。次の順番でしか進めません:

   1. 「アカウント設定」→ **二要素認証（2FA）** を開く
   2. **リカバリコードを生成し、必ず保存する**（テキストファイルやパスワード管理アプリへ）。
      スマホを失くしたときの唯一の復旧手段です
   3. **「Use a recovery code」を押し、保存したコードを1つ入力する**
   4. **「Add 2FA with authentication application」** を押し、表示された QR コードを
      スマホの認証アプリ（Google Authenticator など）で読み取って登録する
   5. 2FA が有効になると、左メニューの **Publishing** が使えるようになります（手順2へ）

> **手順3を飛ばせません。**「Add 2FA with authentication application」のボタンが
> **灰色（取り消し線つき）で押せない**ときは、手順3のリカバリコード確認が未実施です。
> これは「コードをちゃんと保存できているか」を PyPI が確かめるための工程で、
> 入力したコードは1つ消費されます（例: 8 unused → 7 unused）。これは正常な動作です。

> すでにアカウントをお持ちで 2FA も設定済みなら、この手順は不要です。

## 手順2: PyPI に「このリポジトリからの公開を信頼する」と登録する

まだパッケージが存在しない状態で登録するので、**Pending publisher（保留中の公開元）** として登録します。

1. https://pypi.org/manage/account/publishing/ を開く
2. ページ下部の **「Add a new pending publisher」** を探す
3. **GitHub** のタブを選び、次のとおり**正確に**入力する:

   | 入力欄 | 入力する値 |
   |---|---|
   | PyPI Project Name | `ui-hiroba` |
   | Owner | `funakoshi-takehiro` |
   | Repository name | `ui-hiroba` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. **「Add」** を押す

> **ここが一番間違えやすい場所です。** 5つの値が1文字でも違うと、公開時に
> 「invalid-publisher」というエラーで止まります。特に Workflow name は
> `release.yml`（`.github/workflows/` は付けない）、Environment name は `pypi`（小文字）です。

## 手順3: GitHub 側に環境「pypi」を作る

1. https://github.com/funakoshi-takehiro/ui-hiroba/settings/environments を開く
2. **「New environment」** を押す
3. 名前に `pypi` と入力（**手順2で入れた Environment name と完全に同じ**にする）
4. **「Configure environment」** を押して保存する

保護ルール（Required reviewers など）は設定しなくて構いません。タグを push できるのは
リポジトリの権限を持つ人だけなので、これだけで十分安全です。

> 環境を作り忘れると、公開のジョブが動かないか、PyPI 側で拒否されます。

**準備は以上です。**

---

# リリースのたびに行うこと

## 手順A: バージョン番号を上げる

`src/ui_hiroba/__init__.py` の `__version__` を書き換えます。

```python
__version__ = "0.1.0"   # ← ここを上げる
```

番号の付け方の目安:

| 変更内容 | 例 |
|---|---|
| バグ修正・見た目の微調整だけ | `0.1.0` → `0.1.1` |
| 部品や引数が増えた（今までのコードはそのまま動く） | `0.1.1` → `0.2.0` |
| 今までの書き方が動かなくなる変更をした | `0.2.0` → `1.0.0` |

> **同じ番号での再公開はできません。** PyPI は一度公開した番号を永久に予約します。
> 公開後に間違いに気付いたら、削除ではなく**次の番号で公開し直す**のが正しい対処です。

変更をコミットして main に入れます。

## 手順B: タグを打って push する

**バージョン番号の頭に `v` を付けたタグ**を打ちます。これが公開の引き金です。

```bash
git checkout main
git pull origin main
git tag v0.1.0
git push origin v0.1.0
```

## 手順C: 自動公開を見守る

1. https://github.com/funakoshi-takehiro/ui-hiroba/actions を開く
2. **「Release to PyPI」** というワークフローが動き出します（1〜3分ほど）
3. 緑のチェックが付いたら公開完了です

確認:

- https://pypi.org/project/ui-hiroba/ にページができている
- Colab の新しいノートブックで次が通る:

  ```
  !pip install ui-hiroba
  ```

  ```python
  import ui_hiroba as ui
  ui.card("インストール成功", "ui-hiroba が使えます")
  ```

> 公開直後は反映に数分かかることがあります。すぐ見つからなければ少し待ってから再実行してください。

---

# 公開後の使い方

## Google Colab

```
!pip install ui-hiroba
```

セルの先頭で1回実行すれば、そのノートブックで使えるようになります。
（`%pip install` でも同じです。`!` より `%` のほうが確実なので、教材では `%pip` を推奨）

## PyHiroba

PyHiroba には**同梱（vendor）する予定**なので、最終的には
`import ui_hiroba` と書くだけで使えるようになります。同梱前でも、次で入ります:

```
!pip install ui-hiroba
```

PyHiroba は Pyodide（ブラウザ内 Python）なので、内部では `micropip` が PyPI から
wheel を取得します。**このパッケージは純 Python・依存ゼロで `py3-none-any` 形式の
wheel を配布する**ため、そのまま取得できます。学校の閉域網でも、すでに許可されている
`pypi.org` / `files.pythonhosted.org` 以外の通信先は増えません。

---

# うまくいかないときは

| Actions のエラー表示 | 原因と対処 |
|---|---|
| `invalid-publisher` / `not a valid publisher` | 手順2の5つの値のどれかが違います。特に Workflow name（`release.yml`）と Environment name（`pypi`）を確認 |
| `Environment 'pypi' ... waiting` のまま進まない | 手順3の環境が未作成、または名前が違います |
| `File already exists` | そのバージョン番号は公開済みです。手順Aで番号を上げ直して、新しいタグを打ち直してください |
| ワークフロー自体が始まらない | タグの形が違います。`v0.1.0` のように**先頭に `v`** が必要です |
| `403 Forbidden` | 2要素認証が未設定か、Pending publisher の登録が完了していません |

PyPI の画面で進めなくなったときは:

| 症状 | 原因と対処 |
|---|---|
| 「Add 2FA with authentication application」が灰色で押せない | リカバリコードの確認が未実施です。青枠の **「Use a recovery code」** を押し、保存したコードを1つ入力してください（手順1-4の3） |
| 左メニューの Publishing に入れない／登録フォームが出ない | 2FA の設定が未完了です。手順1-4 を最後まで終わらせてください |
| リカバリコードを保存し忘れた | 2FA 設定前なら **「再生成」** で作り直せます（古いコードは無効になります） |

タグを打ち間違えたときは、消してから打ち直せます:

```bash
git tag -d v0.1.0                # 手元のタグを削除
git push origin :refs/tags/v0.1.0  # GitHub 上のタグを削除
```

---

# 補足: 何が公開されるのか

`python -m build` が作る2つのファイルだけです（テストやノートブックは含まれません）:

- `ui_hiroba-0.1.0-py3-none-any.whl` — 実際にインストールされる本体
- `ui_hiroba-0.1.0.tar.gz` — ソース一式

手元で中身を確認したいときは:

```bash
pip install build twine
python -m build          # dist/ に2つのファイルができる
twine check dist/*       # PyPI が受け付ける形式かチェック
```

初回の公開が成功すると、PyPI 側の Pending publisher は通常の Publisher に自動で昇格します。
2回目以降は手順A〜Cだけで公開できます。
