# メタデータ移行ガイド

## 概要

このガイドでは、ベクトルDB（ChromaDB）からMySQLへのメタデータ移行手順を説明します。

## 変更の背景

### 問題点

従来の実装では、楽曲のメタデータ（ファイル名、曲名、アーティスト、ソースディレクトリなど）をすべてChromaDBに格納していました。これにより以下の問題が発生していました：

1. **検索性能の悪化**: キーワード検索時に100,000件のレコードをメモリ上に取得してPython側でフィルタリングする必要があった
2. **あいまい検索の不可**: ChromaDBのメタデータフィルタでは部分一致検索が困難
3. **スケーラビリティの制限**: 楽曲数が増加するとメモリ消費が増大

### 解決策

- **ChromaDB**: 楽曲ID、特徴量ベクトル、検索除外フラグのみを保持
- **MySQL**: すべてのメタデータを保持し、SQLのインデックスとクエリ機能を活用

## アーキテクチャの変更

### 変更前

```
ChromaDB
├── song_id
├── embedding (ベクトル)
└── metadata
    ├── filename
    ├── song_title
    ├── artist_name
    ├── source_dir
    ├── youtube_id
    ├── file_extension
    ├── file_size_mb
    ├── registered_at
    └── excluded_from_search
```

### 変更後

```
ChromaDB
├── song_id
├── embedding (ベクトル)
└── metadata
    └── excluded_from_search (検索除外フラグのみ)

MySQL
├── songs テーブル
│   ├── song_id (PK)
│   ├── filename
│   ├── song_title
│   ├── artist_name
│   ├── source_dir
│   ├── youtube_id
│   ├── file_extension
│   ├── file_size_mb
│   ├── registered_at
│   └── excluded_from_search
└── processed_collections テーブル
    ├── id (PK, AUTO_INCREMENT)
    ├── song_id (FK -> songs.song_id)
    ├── collection_name
    └── processed_at
```

## 移行手順

### 1. データベーステーブルの作成

```bash
cd /home/runner/work/song-recommender/song-recommender
uv run python init_database.py
```

このスクリプトは以下を実行します：
- `songs` テーブルの作成
- `processed_collections` テーブルの作成
- 既存のChromaDBデータからMySQLへのメタデータ移行（オプション）

### 2. 既存データの移行

`init_database.py` を実行すると、既存のChromaDBからMySQLへメタデータを移行するか確認されます。

- `y` を入力すると移行が実行されます
- `N` を入力すると移行をスキップします（新規環境の場合）

### 3. 新しいコードのデプロイ

すべてのコード変更がデプロイされていることを確認してください。

## 主な変更点

### 新しいモジュール

- **`core/song_metadata_db.py`**: MySQLでのメタデータ管理を行う新しいモジュール
  - `add_song()`: 楽曲メタデータをMySQLに追加
  - `get_song()`: song_idで楽曲を取得
  - `search_by_keyword()`: SQL LIKEを使用したキーワード検索
  - `mark_as_processed()`: コレクションごとの処理済みフラグを管理

### 更新されたモジュール

- **`core/db_manager.py`**: ChromaDBの操作を最小限に
  - `add_song()`: excluded_from_searchフラグのみを受け取る
  - `update_excluded_from_search()`: メタデータ更新をシンプル化
  - `get_by_youtube_id()`, `search_by_keyword()` を削除（MySQLに移行）

- **`register_songs.py`**: 二重登録
  - MySQLにメタデータを保存
  - ChromaDBにはベクトルと最小限のメタデータを保存
  - `ProcessedCollection` テーブルで処理済み管理

- **UIページ**: メタデータ取得をMySQLから実行
  - `pages/1_🎵_楽曲検索.py`: SQL ORDER BY、RAND()を使用
  - `pages/3_🗄️_DBメンテナンス.py`: MySQL + ChromaDB同期更新
  - `create_playlist_from_chain.py`: バッチメタデータ取得

## パフォーマンス改善

### 検索パフォーマンス

**変更前**:
```python
# 100,000件をメモリに読み込んでPythonでフィルタ
result = db.list_all(limit=100000)
matches = [song for song in result if keyword in song["metadata"]["song_title"]]
```

**変更後**:
```python
# MySQLでインデックスを使用した高速検索
songs = song_metadata_db.search_by_keyword(keyword, limit=1000)
```

### メモリ使用量

- **変更前**: キーワード検索時に100,000件のメタデータをメモリに保持
- **変更後**: 必要な件数のみSQLでフィルタして取得

## 互換性

### 後方互換性

既存のChromaDBデータは `init_database.py` スクリプトでMySQLに移行可能です。移行後も ChromaDB のデータはそのまま残ります（削除されません）。

### 注意点

1. **環境変数**: MySQL接続情報が `.env` ファイルに設定されていることを確認
2. **依存関係**: `pymysql` と `cryptography` がインストールされていることを確認
3. **データベース接続**: MySQLサーバーが起動していることを確認

## トラブルシューティング

### MySQLに接続できない

```bash
# .envファイルを確認
cat .env.example

# MySQL接続テスト
uv run python -c "from core.database import init_database; init_database()"
```

### 移行が失敗する

```bash
# テーブルを削除して再作成
mysql -u root -p song_recommender
DROP TABLE processed_collections;
DROP TABLE songs;

# 再度init_database.pyを実行
uv run python init_database.py
```

### 検索結果が表示されない

1. MySQLにデータが移行されているか確認
2. `excluded_from_search` フラグがすべて `False` になっているか確認

```sql
SELECT COUNT(*) FROM songs WHERE excluded_from_search = 0;
```

## 今後の拡張性

この変更により、以下の機能拡張が容易になりました：

1. **楽曲タグ付け**: `songs` テーブルに `tags` カラムを追加可能
2. **プレイリスト機能**: MySQLで楽曲とプレイリストの関係を管理
3. **ユーザー評価**: 楽曲への評価やお気に入り機能
4. **高度な検索**: 複数条件の組み合わせ、範囲検索など
5. **統計情報**: SQL集計関数を使用した楽曲統計

## 関連ファイル

- `core/models.py`: SQLAlchemy モデル定義
- `core/song_metadata_db.py`: メタデータ管理モジュール
- `init_database.py`: データベース初期化・移行スクリプト
- `MIGRATION_GUIDE.md`: このドキュメント
