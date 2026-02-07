# プレイリスト作成のユーザー認証対応実装ガイド

このドキュメントでは、プレイリスト作成機能をユーザーごとのYouTube Music認証に対応させた実装について説明します。

## 問題の背景

### 修正前の状態

- プレイリスト作成時に `browser.json` という固定の認証ファイルを使用
- このファイルは開発者のGoogle アカウント認証情報を含む
- 結果として、すべてのユーザーのプレイリストが開発者のアカウントで作成されていた

### 修正後の状態

- 各ユーザーが自分のYouTube Music OAuth認証を設定可能
- プレイリストはログインユーザーのYouTube Musicアカウントに作成される
- 認証情報はデータベースに安全に保存される

## 実装の概要

### 1. データベーススキーマの変更

新しいテーブル `user_ytmusic_auth` を追加：

```sql
CREATE TABLE user_ytmusic_auth (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_sub VARCHAR(200) UNIQUE NOT NULL,
    oauth_json TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (user_sub) REFERENCES user_identities(user_sub) ON DELETE CASCADE,
    INDEX idx_ytmusic_user_sub (user_sub),
    INDEX idx_ytmusic_updated_at (updated_at)
);
```

### 2. 新規モジュール

#### `core/user_ytmusic_auth.py`

ユーザーごとのOAuth認証情報を管理するモジュール：

- `save_user_oauth(user_sub, oauth_json_str)`: OAuth情報を保存
- `get_user_oauth(user_sub)`: OAuth情報を取得（辞書形式）
- `delete_user_oauth(user_sub)`: OAuth情報を削除
- `has_user_oauth(user_sub)`: OAuth情報の存在確認

### 3. 既存モジュールの変更

#### `core/models.py`

`UserYouTubeMusicAuth` モデルを追加：

```python
class UserYouTubeMusicAuth(Base):
    __tablename__ = "user_ytmusic_auth"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_sub: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    oauth_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

#### `core/ytmusic_manager.py`

`YTMusicManager` クラスの初期化を変更：

- `oauth_dict` パラメータを追加（ユーザー固有のOAuth情報を受け取る）
- `browser_file` パラメータを保持（後方互換性のため）
- OAuth情報を一時ファイルに書き込んでYTMusicに渡す

```python
def __init__(self, browser_file: str = "browser.json", oauth_dict: dict | None = None):
    if oauth_dict:
        # ユーザー固有のOAuth認証を使用
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(oauth_dict, tmp)
            tmp_path = tmp.name
        try:
            self.yt = YTMusic(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    else:
        # 後方互換性: browser.json を使用
        self.yt = YTMusic(browser_file)
```

#### `pages/1_🎵_楽曲検索.py`

プレイリスト作成部分を修正：

```python
# ユーザーのOAuth認証情報を取得
user_sub = getattr(st.user, "sub", "")
user_oauth = get_user_oauth(user_sub) if user_sub else None

if not user_oauth:
    st.error("❌ YouTube Music 認証が設定されていません")
    st.info("ユーザー設定ページでYouTube Music認証を設定してください")
else:
    ytmusic = YTMusicManager(oauth_dict=user_oauth)
    # プレイリスト作成処理...
```

#### `pages/8_⚙️_ユーザー設定.py`

YouTube Music認証セクションを追加：

- 認証状態の表示
- OAuth JSONファイルのアップロード機能
- 認証解除ボタン

### 4. ドキュメント

#### `YOUTUBE_OAUTH_SETUP.md`

ユーザー向けのOAuth設定手順：

1. Google Cloud Consoleでプロジェクト作成
2. YouTube Data API v3の有効化
3. OAuth 2.0 クライアントIDの作成
4. OAuth認証ファイルの生成
5. アプリへのアップロード

#### `add_user_ytmusic_auth_table.py`

データベースマイグレーションスクリプト：

```bash
uv run python add_user_ytmusic_auth_table.py
```

## セットアップ手順（管理者向け）

### 1. データベースマイグレーション

```bash
cd /path/to/song-recommender
uv run python add_user_ytmusic_auth_table.py
```

### 2. 依存関係の確認

`pyproject.toml` に以下が含まれていることを確認：

```toml
dependencies = [
    "ytmusicapi>=1.11.5",
    "sqlalchemy>=2.0.0",
    "pymysql>=1.1.0",
]
```

### 3. アプリの再起動

変更を適用するためにアプリを再起動：

```bash
streamlit run app.py
```

## ユーザー向けの使い方

### 1. 認証設定

1. アプリにログイン
2. 「ユーザー設定」（⚙️）ページに移動
3. 「YouTube Music 認証」セクションまでスクロール
4. [YouTube Music OAuth 設定ガイド](YOUTUBE_OAUTH_SETUP.md) に従って `oauth.json` を生成
5. 生成した `oauth.json` をアップロード

### 2. プレイリスト作成

1. 「楽曲検索」ページで曲を検索
2. 連鎖検索を実行
3. プレイリスト名を入力
4. 「YouTube Musicプレイリスト作成」ボタンをクリック
5. プレイリストが自分のYouTube Musicアカウントに作成される

### 3. 認証解除

1. 「ユーザー設定」ページに移動
2. 「認証を解除」ボタンをクリック
3. 認証情報がデータベースから削除される（既存のプレイリストは削除されない）

## セキュリティ考慮事項

### OAuth情報の保護

- OAuth情報はデータベースのTEXT型カラムに保存
- ユーザーごとに分離され、他のユーザーからはアクセス不可
- FOREIGN KEYでユーザーIDと紐付け、ユーザー削除時に自動削除（CASCADE）

### 一時ファイルの処理

- OAuth情報を `YTMusic` に渡す際、一時ファイルを使用
- `tempfile.NamedTemporaryFile` で安全な一時ファイル作成
- 使用後は確実に削除（`finally` ブロックで保証）

### アクセス制御

- OAuth情報は `user_sub` と紐付けられ、ログインユーザーのみアクセス可能
- Streamlit の `st.user` でユーザー識別

## トラブルシューティング

### 認証エラーが発生する

**原因:**
- OAuth情報が期限切れ
- OAuth情報が無効

**対処法:**
1. ユーザー設定で認証を解除
2. 新しい `oauth.json` を生成
3. 再度アップロード

### プレイリスト作成に失敗する

**原因:**
- YouTube Music APIのクォータ制限
- ネットワークエラー
- 認証情報の問題

**対処法:**
1. しばらく待ってから再試行
2. ユーザー設定で認証状態を確認
3. 必要に応じて認証を再設定

### データベースマイグレーションエラー

**原因:**
- データベース接続設定が正しくない
- テーブルが既に存在する

**対処法:**
1. `.env` ファイルのデータベース設定を確認
2. `checkfirst=True` により既存テーブルはスキップされる
3. 手動でテーブルを削除してから再実行（注意: データが失われます）

## 後方互換性

### CLIスクリプト

`create_playlist_from_chain.py` は引き続き `browser.json` を使用：

```python
# レガシーモード
ytm = YTMusicManager(browser_file=BROWSER_FILE)
```

これにより、既存のCLIワークフローは影響を受けません。

### 段階的な移行

- 既存ユーザーは引き続き開発者アカウントでプレイリストを作成可能
- 新しい認証を設定したユーザーから、自分のアカウントでプレイリストを作成
- `browser.json` は保持されるため、既存の動作は維持される

## テスト計画

### 単体テスト

1. `core/user_ytmusic_auth.py` の各関数
   - `save_user_oauth`: 正常系・異常系
   - `get_user_oauth`: 存在する場合・しない場合
   - `delete_user_oauth`: 存在する場合・しない場合
   - `has_user_oauth`: 存在チェック

2. `core/ytmusic_manager.py`
   - `oauth_dict` を使用した初期化
   - `browser_file` を使用した初期化（後方互換性）

### 結合テスト

1. 認証設定フロー
   - OAuth JSONファイルのアップロード
   - 認証状態の表示
   - 認証解除

2. プレイリスト作成フロー
   - ユーザー認証ありでの作成
   - ユーザー認証なしでのエラー表示

3. データベース
   - マイグレーションスクリプトの実行
   - テーブル作成の確認
   - FOREIGN KEY制約の動作確認

### E2Eテスト

1. 新規ユーザーの完全フロー
   - アカウント作成 → ログイン → OAuth設定 → プレイリスト作成

2. 既存ユーザーの移行フロー
   - ログイン → OAuth設定 → プレイリスト作成

## まとめ

この実装により：

✅ ユーザーごとに独立したYouTube Music認証が可能
✅ プレイリストが自分のアカウントに作成される
✅ セキュアに認証情報を管理
✅ 既存機能への影響を最小化（後方互換性）
✅ わかりやすいユーザーインターフェース
✅ 詳細なドキュメントとセットアップガイド

これで、ユーザーは自分のYouTube Musicアカウントでプレイリストを作成できるようになりました。
