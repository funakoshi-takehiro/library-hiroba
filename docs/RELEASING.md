# 公開手順（PyPI へのリリース）

GitHub Actions と PyPI が直接信頼関係を結ぶ Trusted Publishing のしくみで公開します。API トークンをリポジトリに置く必要はありません。費用もかかりません。

準備は最初の1回で済みます。2回目以降はタグを打てば公開されます。

## 旧名 `ui-hiroba` について（記録）

このライブラリは `ui-hiroba` という名前で公開していました。0.3.0 から `library-hiroba` に改名し、旧名は PyPI から削除しました。互換は残していないため、`import ui_hiroba` は動きません。

改名のときに分かったことを、同じ作業をする場合のために残しておきます。

- Trusted Publisher はプロジェクト名ごとの設定です。旧名で登録したものは新しい名前には効かないため、登録をやり直す必要があります
- 順番が決まっています。GitHub のリポジトリ名を先に変えてから、PyPI に登録してください。公開のとき、GitHub は「どのリポジトリから来たか」を実際の名前で名乗ります。登録した Repository name がそれと違うと `invalid-publisher` で止まります。古い名前のままでも push はリダイレクトされるので、気付きにくい取り違えです
- GitHub の環境 `pypi` は、リポジトリ名を変えてもそのまま残ります。作り直しは不要です

---

# 最初の1回だけ行う準備

## 手順1: PyPI のアカウントを作る

1. https://pypi.org/account/register/ で登録し、届いたメールでアドレスを確認する
2. 二要素認証（2FA）を設定する。次の順番でしか進めません:
   1. 「アカウント設定」の二要素認証（2FA）を開く
   2. リカバリコードを生成し、必ず保存する（スマホを失くしたときの唯一の復旧手段です）
   3. 「Use a recovery code」を押し、保存したコードを1つ入力する
   4. 「Add 2FA with authentication application」で認証アプリの QR コードを読み取る

手順2-3を飛ばすことはできません。「Add 2FA with authentication application」が灰色で押せない場合は、リカバリコードの確認が済んでいない状態です。入力したコードは1つ消費されます（例: 8 unused から 7 unused）。これは正常な動作です。

## 手順2: PyPI に公開元を登録する

パッケージがまだ無い状態で登録するので、Pending publisher として登録します。

1. https://pypi.org/manage/account/publishing/ を開く
2. 「Add a new pending publisher」で GitHub のタブを選び、次のとおり正確に入力する

   | 入力欄 | 入力する値 |
   |---|---|
   | PyPI Project Name | `library-hiroba` |
   | Owner | `funakoshi-takehiro` |
   | Repository name | `library-hiroba` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

3. 「Add」を押す

5つの値が1文字でも違うと、公開時に `invalid-publisher` というエラーで止まります。Workflow name は `release.yml` だけを入力し、`.github/workflows/` は付けません。Environment name は小文字の `pypi` です。

## 手順3: GitHub に環境「pypi」を作る

https://github.com/funakoshi-takehiro/ui-hiroba/settings/environments で「New environment」を押し、手順2と同じ `pypi` という名前で作成します。保護ルールの設定は不要です。

---

# リリースのたびに行うこと

## 手順A: バージョン番号を上げる

`src/library_hiroba/__init__.py` の `__version__` を書き換え、main にコミットします。

| 変更内容 | 例 |
|---|---|
| バグ修正・見た目の微調整 | `0.1.0` → `0.1.1` |
| 部品や引数が増えた（今までのコードはそのまま動く） | `0.1.1` → `0.2.0` |
| 今までの書き方が動かなくなる変更 | `0.2.0` → `1.0.0` |

PyPI は一度公開した番号を永久に予約するため、同じ番号での再公開はできません。公開後に間違いに気付いた場合は、次の番号で公開し直します。

## 手順B: タグを打って push する

バージョン番号の頭に `v` を付けたタグが、公開の引き金です。

```bash
git checkout main
git pull origin main
git tag v0.1.0
git push origin v0.1.0
```

## 手順C: 結果を確認する

https://github.com/funakoshi-takehiro/ui-hiroba/actions で「Release to PyPI」が動きます（1〜3分）。ワークフローはタグと `__version__` の照合、lint とテスト、`twine check` を通してから公開します。

緑のチェックが付いたら、https://pypi.org/project/library-hiroba/ と、Colab での `!pip install library-hiroba` を確認します。反映には数分かかることがあります。

---

# うまくいかないときは

| 表示 | 原因と対処 |
|---|---|
| `invalid-publisher` | 手順2の5つの値のどれかが違います。Workflow name と Environment name を確認してください |
| `Environment 'pypi' ... waiting` のまま進まない | 手順3の環境が未作成か、名前が違います |
| `File already exists` | そのバージョン番号は公開済みです。手順Aで番号を上げ、タグを打ち直してください |
| ワークフローが始まらない | タグの形が違います。`v0.1.0` のように先頭に `v` が必要です |
| タグと `__version__` が一致しないというエラー | どちらかを直してからタグを打ち直してください |

タグを打ち間違えた場合は、次で消してから打ち直せます。

```bash
git tag -d v0.1.0
git push origin :refs/tags/v0.1.0
```

PyPI の画面で進めなくなった場合は、次を確認してください。

| 症状 | 原因と対処 |
|---|---|
| 「Add 2FA with authentication application」が灰色で押せない | 「Use a recovery code」でリカバリコードを1つ入力してください（手順1-2の3） |
| Publishing のページに入れない | 2FA の設定が未完了です |
| リカバリコードを保存し忘れた | 2FA 設定前なら「再生成」で作り直せます（古いコードは無効になります） |

---

# 補足

公開されるのは `python -m build` が作る2つのファイルだけです。

- `library_hiroba-0.1.0-py3-none-any.whl` — 実際にインストールされる本体。`src/library_hiroba/` の中身だけが入ります
- `library_hiroba-0.1.0.tar.gz` — ソース一式。テスト・ノートブック・ワークフローも含みます

手元で確認する場合は次を実行します。

```bash
pip install -e ".[dev]"
python -m build
twine check dist/*
```

初回の公開が成功すると、Pending publisher は通常の Publisher に自動で昇格します。
