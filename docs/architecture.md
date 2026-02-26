# アーキテクチャ概要

## ディレクトリ構成

```
song-recommender/
├── backend/                # FastAPI バックエンド
│   ├── main.py             # FastAPI アプリ本体（APIエンドポイント定義）
│   ├── observability.py    # ロギング・リクエストID
│   ├── config.py           # MySQL / ChromaDB 接続設定
│   ├── pyproject.toml      # Python 依存関係（fastapi, uvicorn, chromadb, ...）
│   ├── Dockerfile          # バックエンドコンテナビルド定義
│   ├── core/               # コアビジネスロジック（DBアクセス・特徴量抽出）
│   └── tests/              # テストコード
│
├── frontend/               # Next.js フロントエンド
│   ├── src/
│   │   ├── app/            # App Router ページ
│   │   ├── components/     # UI コンポーネント
│   │   ├── lib/
│   │   │   ├── api-client.ts   # FastAPI へのリクエスト関数群
│   │   │   └── formatters.ts   # 日時等の表示フォーマッタ
│   │   └── types/api.ts    # API レスポンス型定義
│   ├── next.config.ts      # rewrites: /api/* → backend:8080/api/*
│   ├── Dockerfile          # フロントエンドコンテナビルド定義
│   └── package.json
│
├── scripts/                # 曲登録・CLI ツール（別PCで手動実行）
│   ├── register_songs.py       # 音声ファイルをDB登録（メイン）
│   ├── register_songs_local.py # ローカルディレクトリから登録
│   ├── register_segments_mert.py # MERT/AST セグメント登録
│   ├── create_playlist_from_chain.py # 連鎖検索 → YTMusicプレイリスト作成
│   ├── main.py                 # 連鎖検索 CLI
│   └── create_dl_script_from_yt.py   # YouTube DL スクリプト生成
│
├── migration/              # DB マイグレーションスクリプト
├── docs/                   # ドキュメント（このディレクトリ）
├── docker-compose.yml      # 本番環境一括起動
└── pyproject.toml          # スクリプト用 Python 依存関係

```

## コンポーネント間の関係

```
ブラウザ
  │  HTTPS
  ▼
Next.js (frontend:3000)
  │  /api/* を rewrites
  │  サーバーサイドは直接 API_BASE_URL
  ▼
FastAPI (backend:8080)
  ├── MySQL (mysql:3306)         ← 楽曲メタデータ / プレイリスト履歴
  └── ChromaDB (chromadb:8000)  ← 音声特徴量ベクトル

別PCで手動実行
  scripts/ → ChromaDB & MySQL に直接書き込み
```

## ChromaDB コレクション

| コレクション名       | 次元 | 用途               |
|---------------------|------|--------------------|
| songs_minimal       | 15   | テンポ・明るさ重視 |
| songs_balanced      | 33   | 汎用（推奨）       |
| songs_full          | 72   | 詳細マッチング     |
| songs_segments_mert | 可変 | MERT セグメント    |
| songs_segments_ast  | 可変 | AST セグメント     |

## 主要 API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/stats/overview` | 統計概要（曲数・チャンネル数・キュー状態） |
| GET | `/api/stats/playlists` | プレイリスト統計（人気曲・アーティスト） |
| GET | `/api/stats/db-collections` | コレクション別登録曲数 |
| GET | `/api/songs` | 楽曲一覧（キーワード検索・ページネーション対応） |
| GET | `/api/songs/{id}/similar` | 類似曲検索（full/balance/minimal 選択可） |
| GET | `/api/songs/{id}/similar-segments` | セグメント類似検索（mert/ast 選択可） |
| GET | `/api/playlists/history` | プレイリスト履歴一覧 |
| POST | `/api/playlists/create` | YouTube Music プレイリスト作成 |
