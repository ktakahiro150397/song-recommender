# ===== ビルドステージ: 依存関係のインストール =====
FROM python:3.12-slim AS builder

WORKDIR /app

# uv をインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 依存関係ファイルをコピー
COPY pyproject.toml uv.lock ./

# 依存関係をインストール
RUN uv sync --frozen --no-dev

# ===== 実行ステージ: 最小限のランタイム環境 =====
FROM python:3.12-slim

WORKDIR /app

# システム依存パッケージをインストール（librosaに必要）
# 最小限のパッケージのみインストールしてキャッシュをクリーンアップ
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# uv をコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ビルダーステージから依存関係をコピー
COPY --from=builder /app/.venv /app/.venv

# アプリケーションコードをコピー
COPY app.py config.py create_playlist_from_chain.py ./
COPY core/ ./core/
COPY pages/ ./pages/
COPY .streamlit/ ./.streamlit/

# データディレクトリとアップロードディレクトリを作成
RUN mkdir -p /app/data /app/upload/data

# 環境変数の設定
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Streamlit用ポートを公開
EXPOSE 8501

# ヘルスチェック
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Streamlitを起動
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
