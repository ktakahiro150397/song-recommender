# Python 3.12 slim イメージをベースに使用
FROM python:3.12-slim

# 作業ディレクトリを設定
WORKDIR /app

# システム依存パッケージをインストール（librosaに必要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# uv をインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 依存関係ファイルをコピー
COPY pyproject.toml uv.lock ./

# 依存関係をインストール（キャッシュ効率のため先にインストール）
RUN uv sync --frozen --no-dev

# アプリケーションコードをコピー
COPY app.py home_page.py config.py create_playlist_from_chain.py ./
COPY core/ ./core/
COPY pages/ ./pages/
COPY .streamlit/ ./.streamlit/

# データディレクトリとアップロードディレクトリを作成
RUN mkdir -p /app/data /app/upload/data

# Streamlit用ポートを公開
EXPOSE 8501

# ヘルスチェック
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Streamlitを起動
CMD ["uv", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
