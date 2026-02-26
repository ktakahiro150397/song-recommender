# セットアップガイド

## 必要なもの

- Docker & Docker Compose
- `.env` ファイル（`.env.example` をコピーして作成）
- YouTube Music 認証ファイル（`oauth.json` または `browser.json`）

## 環境変数

`.env.example` を `.env` にコピーして以下を設定：

```bash
cp .env.example .env
```

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `MYSQL_ROOT_PASSWORD` | MySQL root パスワード | `rootpassword` |
| `MYSQL_DATABASE` | データベース名 | `song_recommender` |
| `MYSQL_USER` | アプリ用ユーザー | `app_user` |
| `MYSQL_PASSWORD` | アプリ用パスワード | `app_password` |
| `CHROMA_HOST` | ChromaDB ホスト | `chromadb` |
| `CHROMA_PORT` | ChromaDB ポート | `8000` |
| `NEXTAUTH_SECRET` | NextAuth 署名キー | ※必須 |
| `GOOGLE_CLIENT_ID` | Google OAuth クライアントID | ※必須 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth シークレット | ※必須 |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel トークン | 任意 |

## 起動

```bash
# 初回（DBマイグレーション）
docker compose up mysql chromadb -d
uv run python migration/init_database.py

# 全サービス起動
docker compose up -d
```

## アクセス先

| サービス | URL |
|---------|-----|
| フロントエンド (Next.js) | http://localhost:3000 |
| バックエンド (FastAPI) | http://localhost:8080 |
| API ドキュメント | http://localhost:8080/docs |
| ChromaDB | http://localhost:8000 |
| MySQL | localhost:33306 |

## 開発環境（ローカル）

### バックエンド

```bash
cd backend
uv run uvicorn main:app --reload --port 8080
```

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

`.env.local` を `frontend/` に作成して API URL を設定：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
```
