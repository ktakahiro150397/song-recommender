"""
設定ファイル

アプリケーション全体で使用する定数を管理
"""

from pathlib import Path

# ========== パス設定 ==========

# アップロードファイルの保存先ディレクトリ
UPLOAD_DATA_DIR = Path("upload/data")

# ベクトルDB設定
DB_CONFIGS = [
    {"path": "data/chroma_db_cos_minimal", "mode": "minimal"},
    {"path": "data/chroma_db_cos_balance", "mode": "balanced"},
    {"path": "data/chroma_db_cos_full", "mode": "full"},
]

# DB パス（連鎖検索等で使用）
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
