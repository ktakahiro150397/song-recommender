"""
YouTubeチャンネルURL管理用のSQLiteデータベース操作モジュール
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse


class ChannelDB:
    """YouTubeチャンネルURLを管理するクラス"""

    def __init__(self, db_path: str = "./data/youtube_channels.db"):
        """
        Args:
            db_path: SQLiteデータベースファイルのパス
        """
        # ディレクトリがなければ作成
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """データベースとテーブルを初期化"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS youtube_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    registered_at TIMESTAMP NOT NULL
                )
            """)
            # インデックスを作成
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_registered_at 
                ON youtube_channels(registered_at DESC)
            """)
            conn.commit()

    @staticmethod
    def validate_youtube_url(url: str) -> tuple[bool, str]:
        """
        YouTubeのURLかどうかを検証する
        
        Args:
            url: 検証するURL
            
        Returns:
            (検証結果, エラーメッセージ) のタプル
        """
        try:
            parsed = urlparse(url)
            
            # スキームチェック
            if parsed.scheme not in ['http', 'https']:
                return False, "URLは http または https で始まる必要があります"
            
            # ドメインチェック
            valid_domains = [
                'www.youtube.com',
                'youtube.com',
                'm.youtube.com',
                'music.youtube.com'
            ]
            
            if parsed.netloc not in valid_domains:
                return False, f"YouTubeのURLを入力してください (有効なドメイン: {', '.join(valid_domains)})"
            
            # パスチェック（チャンネルURL形式かどうか）
            path = parsed.path
            valid_patterns = ['/channel/', '/@', '/c/', '/user/']
            
            if not any(path.startswith(pattern) for pattern in valid_patterns):
                return False, "チャンネルURLの形式が正しくありません (例: /channel/xxx, /@username, /c/xxx, /user/xxx)"
            
            return True, ""
            
        except Exception as e:
            return False, f"URL解析エラー: {str(e)}"

    def add_channel(self, url: str) -> tuple[bool, str]:
        """
        チャンネルURLを登録する
        
        Args:
            url: YouTubeチャンネルのURL
            
        Returns:
            (成功/失敗, メッセージ) のタプル
        """
        # URL検証
        is_valid, error_msg = self.validate_youtube_url(url)
        if not is_valid:
            return False, error_msg
        
        # 登録
        try:
            with sqlite3.connect(self.db_path) as conn:
                registered_at = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO youtube_channels (url, registered_at) VALUES (?, ?)",
                    (url, registered_at)
                )
                conn.commit()
                return True, "チャンネルURLを登録しました"
                
        except sqlite3.IntegrityError:
            return False, "このURLは既に登録されています"
        except Exception as e:
            return False, f"登録エラー: {str(e)}"

    def get_all_channels(self) -> list[dict]:
        """
        登録されている全チャンネルを取得する（新しい順）
        
        Returns:
            チャンネル情報のリスト
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, url, registered_at 
                FROM youtube_channels 
                ORDER BY registered_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def delete_channel(self, channel_id: int) -> tuple[bool, str]:
        """
        チャンネルを削除する
        
        Args:
            channel_id: 削除するチャンネルのID
            
        Returns:
            (成功/失敗, メッセージ) のタプル
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM youtube_channels WHERE id = ?",
                    (channel_id,)
                )
                conn.commit()
                
                if cursor.rowcount > 0:
                    return True, "チャンネルを削除しました"
                else:
                    return False, "指定されたチャンネルが見つかりません"
                    
        except Exception as e:
            return False, f"削除エラー: {str(e)}"

    def get_channel_count(self) -> int:
        """
        登録されているチャンネル数を取得する
        
        Returns:
            チャンネル数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM youtube_channels")
            return cursor.fetchone()[0]

    def channel_exists(self, url: str) -> bool:
        """
        指定されたURLが既に登録されているかチェックする
        
        Args:
            url: チェックするURL
            
        Returns:
            存在する場合True
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM youtube_channels WHERE url = ?",
                (url,)
            )
            return cursor.fetchone()[0] > 0
