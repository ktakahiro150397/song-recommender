# YouTube Music プレイリスト作成機能 セットアップガイド

このガイドでは、管理者がYouTube Music APIの認証を設定する手順を説明します。

## 概要

ユーザーがStreamlitアプリにGoogleアカウントでログインする際に、YouTube Music APIの権限も同時に取得します。これにより、ユーザーは自分のYouTube Musicアカウントにプレイリストを作成できます。

## 前提条件

- Google Cloud Consoleへのアクセス権限
- Streamlit 1.42.0以上
- Authlib 1.3.2以上

## セットアップ手順

### 1. Google Cloud Consoleでプロジェクトを作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成（または既存のプロジェクトを使用）
3. プロジェクト名を入力（例: "song-recommender"）

### 2. YouTube Data API v3 を有効化

1. Google Cloud Console の左メニューから「APIとサービス」→「ライブラリ」を選択
2. "YouTube Data API v3" を検索
3. APIを選択して「有効にする」をクリック

### 3. OAuth 2.0 クライアントIDを作成

#### OAuth同意画面の設定

1. 左メニューから「APIとサービス」→「OAuth同意画面」を選択
2. ユーザータイプを選択：
   - **外部**: 誰でもアクセス可能（推奨）
   - **内部**: Google Workspaceの組織内のみ
3. アプリ情報を入力：
   - アプリ名: "Song Recommender"（任意）
   - ユーザーサポートメール: 管理者のメールアドレス
   - デベロッパーの連絡先: 管理者のメールアドレス
4. スコープ:
   - 「ADD OR REMOVE SCOPES」をクリック
   - 以下のスコープを追加：
     - `openid`
     - `https://www.googleapis.com/auth/userinfo.email`
     - `https://www.googleapis.com/auth/userinfo.profile`
     - `https://www.googleapis.com/auth/youtube` （YouTube Music プレイリスト作成用）
5. テストユーザー（外部の場合）:
   - 必要に応じてテストユーザーのメールアドレスを追加
   - 本番環境では「公開」ステータスにする必要がある場合があります

#### クライアントIDの作成

1. 左メニューから「APIとサービス」→「認証情報」を選択
2. 「認証情報を作成」→「OAuth クライアント ID」をクリック
3. アプリケーションの種類: **ウェブアプリケーション**
4. 名前: "Song Recommender Web Client"（任意）
5. 承認済みのリダイレクトURIを追加：
   - ローカル開発: `http://localhost:8501/oauth2callback`
   - 本番環境: `https://<あなたのドメイン>/oauth2callback`
6. 「作成」をクリック
7. 表示される **クライアントID** と **クライアントシークレット** をメモ

### 4. Streamlit設定ファイルを作成

プロジェクトのルートに `.streamlit/secrets.toml` ファイルを作成（既に存在する場合は編集）：

```toml
[auth]
# リダイレクトURI（環境に応じて変更）
redirect_uri = "http://localhost:8501/oauth2callback"

# Cookie用のランダムな秘密鍵（下記コマンドで生成）
# python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
cookie_secret = "YOUR_RANDOM_SECRET_HERE"

# アクセストークンを公開（YouTube API呼び出しに必要）
expose_tokens = ["access", "id"]

[auth.google]
# Google Cloud Consoleで取得したクライアントID
client_id = "YOUR_CLIENT_ID_HERE"

# Google Cloud Consoleで取得したクライアントシークレット
client_secret = "YOUR_CLIENT_SECRET_HERE"

# Google OAuth 2.0 メタデータURL
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

# YouTube APIスコープを含むカスタムスコープ
[auth.google.client_kwargs]
scope = "openid profile email https://www.googleapis.com/auth/youtube"
```

#### cookie_secretの生成方法

以下のコマンドでランダムな文字列を生成：

```bash
python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

### 5. 依存関係の確認

`pyproject.toml` に以下の依存関係が含まれていることを確認：

```toml
[project]
dependencies = [
    "streamlit>=1.42.0",
    "authlib>=1.3.2",
    "ytmusicapi>=1.11.5",
    # その他の依存関係...
]
```

### 6. アプリの起動と動作確認

```bash
streamlit run app.py
```

1. ブラウザで `http://localhost:8501` を開く
2. 「Googleでログイン」ボタンをクリック
3. Googleアカウントでログイン
4. 権限の確認画面で「YouTube」へのアクセスを許可
5. ログイン成功後、プレイリスト作成機能が利用可能

## トラブルシューティング

### リダイレクトURIエラー

**症状:** `redirect_uri_mismatch` エラー

**対処法:**
1. Google Cloud Consoleの「承認済みのリダイレクトURI」と `.streamlit/secrets.toml` の `redirect_uri` が一致しているか確認
2. ローカル開発: `http://localhost:8501/oauth2callback`
3. 本番環境: `https://yourdomain.com/oauth2callback`（HTTPSが必須）

### YouTube API 権限エラー

**症状:** プレイリスト作成時に「YouTube API の権限が不足しています」と表示

**対処法:**
1. `.streamlit/secrets.toml` の `client_kwargs.scope` に `https://www.googleapis.com/auth/youtube` が含まれているか確認
2. YouTube Data API v3 が Google Cloud Console で有効になっているか確認
3. 一度ログアウトして再ログイン（権限を再取得）

### アクセストークンが取得できない

**症状:** `st.user.get("access_token")` が `None` を返す

**対処法:**
1. `.streamlit/secrets.toml` の `[auth]` セクションに `expose_tokens = ["access", "id"]` が設定されているか確認
2. Streamlitのバージョンが 1.42.0 以上か確認
3. アプリを再起動

## セキュリティ考慮事項

### secrets.tomlの保護

- `.streamlit/secrets.toml` は **絶対にGitにコミットしない**
- `.gitignore` に `.streamlit/secrets.toml` が含まれていることを確認
- 本番環境では環境変数または安全なシークレット管理サービスを使用

### アクセストークンの扱い

- アクセストークンは有効期限があります（通常1時間）
- **重要**: Streamlit の OIDC 認証では refresh_token が提供されないため、トークンが期限切れになった場合、ユーザーは再ログインする必要があります
- 実装では、トークン期限切れ時にエラーメッセージを表示し、ユーザーに再ログインを促します
- 長時間のセッションでプレイリスト作成を行う場合、定期的なログイン更新が必要になることをユーザーに周知してください

### OAuth 同意画面の公開

- テスト段階では「外部」で問題ありません
- 本番環境で多くのユーザーが利用する場合、Googleの審査を受けて公開する必要がある場合があります

## 本番環境へのデプロイ

### Streamlit Community Cloud

1. リポジトリを GitHub にプッシュ
2. Streamlit Community Cloud でアプリをデプロイ
3. 「Secrets」セクションで `.streamlit/secrets.toml` の内容を設定
4. Google Cloud Console でリダイレクトURIを本番URLに更新

### その他のプラットフォーム

- 環境変数で設定値を管理
- シークレット管理サービス（AWS Secrets Manager, Google Secret Manager等）の使用を検討

## よくある質問

### Q: ユーザーごとに個別のGoogle Cloud プロジェクトが必要ですか？

A: いいえ。管理者が1つのGoogle Cloud プロジェクトを設定すれば、すべてのユーザーがそれを使用してログインできます。

### Q: ユーザーは何か設定する必要がありますか？

A: いいえ。ユーザーはアプリにログインするだけで、自動的にYouTube APIの権限が付与されます。

### Q: プレイリストはどのアカウントに作成されますか？

A: ログインしたユーザー自身のYouTube Musicアカウントに作成されます。

### Q: OAuth同意画面を公開する必要がありますか？

A: テスト段階では不要です。ただし、100人以上のユーザーが利用する場合や、テストユーザー以外がアクセスする場合は、Googleの審査を受けて公開する必要があります。

## 参考リンク

- [Streamlit Authentication Documentation](https://docs.streamlit.io/develop/api-reference/user/st.login)
- [Google Cloud Console](https://console.cloud.google.com/)
- [YouTube Data API v3](https://developers.google.com/youtube/v3)
- [ytmusicapi Documentation](https://ytmusicapi.readthedocs.io/)
