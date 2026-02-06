# Google認証 かんたん導入方針（Streamlit / st.login）

このアプリはStreamlitなので、公式の`st.login()` + `st.user` + `st.logout()`を使うのが最短です。Google側の設定さえ終われば、アプリ側の実装は数行で済みます。

---

## 0. 前提
- 対象アプリ: Streamlit（このリポジトリの`app.py`）
- 使う機能: `st.login()` / `st.user` / `st.logout()`
- 参考記事: https://zenn.dev/datum_studio/articles/c964f9e38379f4

---

## 1. 方針（ざっくり）
1. Google Cloud ConsoleでOAuthクライアントIDを作る。
2. `.streamlit/secrets.toml`に認証設定を書く。
3. `app.py`の先頭で「ログインしてなければログイン画面→`st.login()`」にする。
4. 必要なら「ログイン許可ユーザーのメール」をアプリ側で制限する。

---

## 2. Google Cloud Consoleでやること（最短ルート）
1. Google Cloud Consoleにログイン
2. プロジェクト作成（既存でもOK）
3. 左メニュー「APIとサービス」→「OAuth同意画面」
   - 種別: 個人なら「外部」でOK
   - テストユーザーに自分のGmailを追加（最初はこれで十分）
4. 左メニュー「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuthクライアントID」
   - アプリケーションの種類: **ウェブアプリケーション**
   - 名前: 何でもOK
   - 承認済みのリダイレクトURI:
     - ローカル: `http://localhost:8501/oauth2callback`
     - 本番: `https://<あなたのアプリURL>/oauth2callback`
5. `client_id` と `client_secret` を控える

---

## 3. secrets.tomlを作る（必須）
`<repo>/.streamlit/secrets.toml` を新規作成して、以下を入れる。

```
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "<ランダム文字列>"
client_id = "<Googleで取得したclient_id>"
client_secret = "<Googleで取得したclient_secret>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

### cookie_secretの作り方
PowerShell でもOK。とにかくランダムにすれば良い。

```
python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

### 注意
- `secrets.toml`は**絶対にGitに入れない**
- `.gitignore`に`.streamlit/secrets.toml`が無いなら追加

---

## 4. 依存関係を追加（必要なら）
記事では`Authlib`が必要です。Streamlitも`st.login()`対応版が必要。

`pyproject.toml`の依存に以下を追加（または更新）:

```
streamlit>=1.42.0
authlib>=1.3.2
```

---

## 5. アプリ側の実装（最小）
**結論: `app.py`の先頭でログインチェック**が一番シンプル。

イメージ:

```python
import streamlit as st

if not st.user.is_logged_in:
    st.title("ログイン")
    if st.button("Googleでログイン"):
        st.login()
    st.stop()

if st.button("ログアウト"):
    st.logout()
```

### どこに入れる？
- `app.py`の`st.set_page_config`の直後が無難
- これで全ページがログイン必須になる

---

## 6. 必要なら「許可ユーザー」を絞る
`st.user.email`で制限できる。例:

```python
ALLOWED_EMAILS = {"your@gmail.com"}

if st.user.is_logged_in and st.user.email not in ALLOWED_EMAILS:
    st.error("このアカウントは許可されていません")
    st.logout()
    st.stop()
```

---

## 7. 動作確認チェックリスト
- [ ] `secrets.toml`が存在する
- [ ] `client_id`/`client_secret`が正しい
- [ ] Google側のリダイレクトURIが一致
- [ ] `streamlit run app.py`でログイン画面が出る
- [ ] ログイン後にページが表示される

---

## 8. よくあるハマりどころ
- **リダイレクトURIの不一致** → 9割これ
- **`st.login()`が無い** → Streamlitのバージョンが古い
- **`secrets.toml`の場所ミス** → 必ず`.streamlit/`配下

---

## 9. 次にやること（実装の具体化）
1. `app.py`へログインガードを追加
2. `.streamlit/secrets.toml`を作成
3. `pyproject.toml`を更新（必要なら）

この方針でOKなら、次は**実際にコードを入れる**ところまで進められます。
