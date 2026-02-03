"""
設定ファイル

アプリケーション全体で使用する定数を管理
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# ========== ChromaDB 設定 ==========

# ChromaDB 接続先（Dockerコンテナまたはローカル）
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

# ========== パス設定 ==========

# アップロードファイルの保存先ディレクトリ
UPLOAD_DATA_DIR = Path("upload/data")

# ベクトルDB設定（コレクション名として使用）
DB_CONFIGS = [
    {"collection": "songs_minimal", "mode": "minimal"},
    {"collection": "songs_balanced", "mode": "balanced"},
    {"collection": "songs_full", "mode": "full"},
]

# DB パス（連鎖検索等で使用）- 後方互換性のため残す
DB_PATHS = [
    "data/chroma_db_cos_full",
    "data/chroma_db_cos_balance",
    "data/chroma_db_cos_minimal",
]

# ========== 音声処理設定 ==========

# 音声抽出時間（秒）
AUDIO_DURATION = 90

# 対応する音声フォーマット
SUPPORTED_AUDIO_FORMATS = [".wav", ".mp3"]
