# ===== ビルドステージ =====
FROM python:3.12-slim AS builder

WORKDIR /app

# uv をインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 依存関係ファイルをコピー
COPY pyproject.toml ./

# 依存関係をインストール
RUN uv sync --frozen --no-dev

# ===== 実行ステージ =====
FROM python:3.12-slim

WORKDIR /app

# システム依存パッケージ（librosa用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# uv をコピー
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 依存関係をコピー
COPY --from=builder /app/.venv /app/.venv

# アプリケーションコードをコピー
COPY main.py observability.py config.py ./
COPY core/ ./core/

# データディレクトリを作成
RUN mkdir -p /app/data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK CMD curl --fail http://localhost:8080/api/stats/overview || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
