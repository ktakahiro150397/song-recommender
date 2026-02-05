# Docker Image Size Optimization

## 問題
Dockerイメージのサイズが約500MBと大きすぎる問題がありました。

## 実施した最適化

### 1. マルチステージビルドの導入
- **ビルドステージ**: 依存関係のインストールのみ実行
- **実行ステージ**: ビルド済みの依存関係のみコピー
- 効果: ビルド時の中間ファイルやキャッシュが最終イメージに含まれない

### 2. apt パッケージ管理の最適化
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
```
- `apt-get clean`: パッケージキャッシュのクリーンアップ
- `/var/lib/apt/lists/*`: apt パッケージリストの削除
- `/tmp/*`, `/var/tmp/*`: 一時ファイルの削除

### 3. .dockerignore の改善
不要なファイルをイメージに含めないよう除外:
- テストファイル (`test_*.py`, `debug_*.py`)
- ドキュメント (`*.md`)
- Git履歴 (`.git/`, `.github/`)
- データディレクトリ (`data/`, `upload/`)
- 設定ファイル (`docker-compose.yml`, `.env`)
- メンテナンススクリプト (`migrate_*.py`, `db_maintenance.py`)

### 4. Python環境変数の最適化
```dockerfile
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
```
- `PYTHONDONTWRITEBYTECODE=1`: `.pyc` ファイルの生成を防止
- `PYTHONUNBUFFERED=1`: Python出力のバッファリングを無効化（ログ出力の改善）

### 5. レイヤーキャッシュの最適化
- 依存関係ファイル（`pyproject.toml`, `uv.lock`）を先にコピー
- アプリケーションコードは後でコピー
- 効果: コード変更時に依存関係の再インストールが不要

## 期待される効果

### サイズ削減
- **ビルドキャッシュの除外**: uvキャッシュ、aptキャッシュが含まれない
- **不要ファイルの除外**: テストファイル、ドキュメント等が含まれない
- **マルチステージビルド**: ビルドツールが最終イメージに含まれない

### その他のメリット
- **ビルド時間の短縮**: レイヤーキャッシュの効率的な利用
- **セキュリティ向上**: 不要なファイルを含まないことで攻撃面が減少
- **デプロイの高速化**: イメージサイズが小さいため転送が速い

## ビルド方法

```bash
# イメージのビルド
docker build -t song-recommender:optimized .

# イメージサイズの確認
docker images song-recommender:optimized

# 実行
docker-compose up -d
```

## さらなる最適化の可能性

今後検討可能な追加最適化:

1. **Alpine Linuxベースイメージの使用**
   - 注意: librosaがmusl libcで動作するか確認が必要

2. **依存関係の見直し**
   - 使用していない依存関係の削除
   - より軽量な代替ライブラリの検討

3. **静的ファイルの最適化**
   - フォント、アイコン等の不要なアセットの削除

4. **Python パッケージのスリム化**
   - pip-autoremove等を使用した未使用パッケージの削除
