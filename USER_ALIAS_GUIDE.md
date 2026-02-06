# ユーザーエイリアス機能の追加

## 概要

このアップデートでは、ユーザーがプレイリスト履歴やコメントで表示される名前を自由に設定できる「エイリアス（表示名）」機能が追加されました。

## 変更内容

### 1. データベース変更

`user_identities` テーブルに `alias` カラムを追加しました。

```sql
ALTER TABLE user_identities
ADD COLUMN alias VARCHAR(100) NOT NULL DEFAULT '' AFTER email;
```

### 2. 新機能

#### ユーザー設定ページ（⚙️ ユーザー設定）

- ナビゲーションメニューに「ユーザー設定」ページを追加
- 表示名（エイリアス）を設定・変更できる画面を提供
- 最大100文字まで設定可能

#### 表示名の優先順位

プレイリスト履歴やコメントでのユーザー表示は以下の優先順位で決定されます：

1. **エイリアスが設定されている場合**: エイリアスを表示
2. **エイリアスが未設定の場合**: メールアドレスを表示

### 3. 影響を受けるページ

以下のページで表示名が使用されます：

- **プレイリスト履歴** (`pages/7_📋_プレイリスト履歴.py`)
  - プレイリスト作成者の表示
  - コメント投稿者の表示

### 4. 追加されたAPI

`core/user_db.py` に以下の関数が追加されました：

- `get_display_names_by_subs(user_subs: list[str]) -> dict[str, str]`
  - ユーザーSubから表示名（エイリアスまたはメールアドレス）を取得
  
- `get_user_alias(user_sub: str) -> str`
  - 特定ユーザーのエイリアスを取得
  
- `update_user_alias(user_sub: str, alias: str) -> bool`
  - ユーザーのエイリアスを更新

## 移行手順

### 既存データベースへの適用

1. データベースマイグレーションスクリプトを実行:
   ```bash
   python add_user_alias_column.py
   ```

2. スクリプトは以下を実行します:
   - `user_identities` テーブルに `alias` カラムが存在するかチェック
   - カラムが存在しない場合のみ追加
   - 既存レコードの `alias` は空文字列（デフォルト値）に設定

### 新規データベースの場合

新規にデータベースを作成する場合は、通常の初期化スクリプトで自動的に `alias` カラムが作成されます：

```bash
python init_database.py
```

## 使い方

### エンドユーザー向け

1. アプリケーションにログイン
2. ナビゲーションメニューから「⚙️ ユーザー設定」を選択
3. 「表示名」フィールドに希望する名前を入力（最大100文字）
4. 「保存」ボタンをクリック
5. プレイリスト履歴やコメントで設定した表示名が使用されます

### 表示名のクリア

表示名フィールドを空にして保存すると、元のメールアドレス表示に戻ります。

## 技術的な詳細

### モデル変更

`core/models.py` の `UserIdentity` クラス:

```python
class UserIdentity(Base):
    id: Mapped[int]
    user_sub: Mapped[str]
    email: Mapped[str]
    alias: Mapped[str]  # 新規追加
    updated_at: Mapped[datetime]
```

### 後方互換性

- 既存の `get_emails_by_subs()` 関数は変更されていないため、エイリアス機能を使用しないコードは影響を受けません
- 新しい `get_display_names_by_subs()` 関数を使用することで、エイリアス機能を有効化できます

## ファイル一覧

### 変更されたファイル

- `core/models.py` - UserIdentity モデルに alias フィールドを追加
- `core/user_db.py` - エイリアス関連の関数を追加
- `app.py` - ユーザー設定ページをナビゲーションに追加
- `pages/7_📋_プレイリスト履歴.py` - 表示名を使用するように更新

### 新規ファイル

- `pages/8_⚙️_ユーザー設定.py` - ユーザー設定ページ
- `add_user_alias_column.py` - データベースマイグレーションスクリプト
