# ChromaDB Docker移行ガイド

このドキュメントでは、ChromaDBをローカルファイルベースからDockerコンテナベースに移行する手順を説明します。

## 変更内容

### 1. アーキテクチャの変更

**変更前:**
- ChromaDBはローカルファイルシステムに直接保存（`data/chroma_db_cos_*`）
- 各スクリプトがPersistentClientで個別にDBファイルにアクセス

**変更後:**
- ChromaDBはDockerコンテナとして独立したサービスで実行
- 全スクリプトがHttpClientでリモートChromaDBサーバーに接続
- データは`data/chroma_data/`に永続化
- コレクション名ベースで管理（`songs_minimal`, `songs_balanced`, `songs_full`）

### 2. 環境変数の追加

`.env`ファイルで接続情報を管理:
```env
CHROMA_HOST=chromadb
CHROMA_PORT=8000
```

### 3. docker-compose.ymlの変更

ChromaDBサービスを追加:
```yaml
chromadb:
  image: chromadb/chroma:latest
  ports:
    - "8000:8000"
  volumes:
    - ./data/chroma_data:/chroma/chroma
```

## 既存データの移行手順

### オプション1: 新規にデータを登録し直す（推奨）

1. Dockerコンテナを起動:
   ```powershell
   docker-compose up -d chromadb
   ```

2. データを再登録:
   ```powershell
   uv run register_songs.py --parallel process
   ```

### オプション2: 既存データを移行する

既存のローカルDBデータを新しいChromaDBコンテナに移行する場合:

1. 既存のChromaDBデータを確認:
   ```
   data/
   ├── chroma_db_cos_minimal/
   ├── chroma_db_cos_balance/
   └── chroma_db_cos_full/
   ```

2. ChromaDBコンテナを起動:
   ```powershell
   docker-compose up -d chromadb
   ```

3. 移行スクリプトを実行（未実装の場合は手動で再登録が必要）

## ローカル開発時の注意点

### Dockerを使わない場合

ローカルで開発する際にDockerを使わない場合は、`SongVectorDB`の初期化時に`use_remote=False`を指定:

```python
db = SongVectorDB(
    db_path="data/chroma_db_test",
    collection_name="songs_test",
    use_remote=False
)
```

### Docker環境で実行する場合

docker-compose経由で実行する場合は、自動的にリモートChromaDBに接続されます（`use_remote=True`がデフォルト）。

## トラブルシューティング

### ChromaDBに接続できない

1. ChromaDBコンテナが起動しているか確認:
   ```powershell
   docker-compose ps
   ```

2. ChromaDBのログを確認:
   ```powershell
   docker-compose logs chromadb
   ```

3. ヘルスチェック:
   ```powershell
   curl http://localhost:8000/api/v1/heartbeat
   ```

### 既存のデータが見つからない

既存のローカルDBデータは自動的には移行されません。上記の「既存データの移行手順」を参照してください。

## 依存関係の更新

`python-dotenv`が新しく追加されました:
```powershell
uv sync
```

## 関連ファイル

- [.env](.env) - 環境変数（gitignore対象）
- [.env.example](.env.example) - 環境変数のテンプレート
- [docker-compose.yml](docker-compose.yml) - Docker設定
- [config.py](config.py) - アプリケーション設定
- [core/db_manager.py](core/db_manager.py) - DB接続管理
