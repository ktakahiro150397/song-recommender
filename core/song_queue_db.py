"""
YouTube曲登録キュー管理用のSQLiteデータベース操作モジュール

Streamlitで登録されたYouTube動画URLを保存し、
後からバッチ処理でダウンロード・DB登録を行う
"""

import sqlite3
import re
from pathlib import Path
from datetime import datetime
from typing import Optional


class SongQueueDB:
    """YouTube曲登録キューを管理するクラス"""

    def __init__(self, db_path: str = "./data/song_queue.db"):
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS song_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    title TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    registered_at TIMESTAMP NOT NULL,
                    processed_at TIMESTAMP
                )
            """
            )
            # インデックスを作成
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_status 
                ON song_queue(status)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_registered_at 
                ON song_queue(registered_at DESC)
            """
            )
            conn.commit()

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """
        YouTubeのURLから動画IDを抽出する

        Args:
            url: YouTube URL

        Returns:
            動画ID（11文字）または None
        """
        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|music\.youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})",
            r"^([a-zA-Z0-9_-]{11})$",  # 直接動画IDが入力された場合
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def add_song(
        self, url: str, title: Optional[str] = None
    ) -> tuple[bool, str, Optional[str]]:
        """
        YouTube動画をキューに追加する

        Args:
            url: YouTubeのURL
            title: 曲名（任意）

        Returns:
            (成功/失敗, メッセージ, 動画ID) のタプル
        """
        video_id = self.extract_video_id(url)

        if not video_id:
            return False, "無効なURLです。YouTubeの動画URLを入力してください", None

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO song_queue (video_id, url, title, status, registered_at)
                    VALUES (?, ?, ?, 'pending', ?)
                """,
                    (video_id, url, title, datetime.now()),
                )
                conn.commit()
            return True, f"登録しました: {video_id}", video_id
        except sqlite3.IntegrityError:
            return False, f"既に登録済みです: {video_id}", video_id

    def get_pending_songs(self) -> list[dict]:
        """
        未処理の曲リストを取得

        Returns:
            未処理の曲情報のリスト
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, video_id, url, title, status, registered_at
                FROM song_queue
                WHERE status = 'pending'
                ORDER BY registered_at ASC
            """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_songs(self, limit: int = 100) -> list[dict]:
        """
        全ての曲リストを取得

        Args:
            limit: 取得件数の上限

        Returns:
            曲情報のリスト
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, video_id, url, title, status, registered_at, processed_at
                FROM song_queue
                ORDER BY registered_at DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def mark_as_processed(self, video_id: str) -> bool:
        """
        曲を処理済みにマークする

        Args:
            video_id: 動画ID

        Returns:
            成功したかどうか
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE song_queue
                SET status = 'processed', processed_at = ?
                WHERE video_id = ?
            """,
                (datetime.now(), video_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_as_failed(self, video_id: str) -> bool:
        """
        曲を失敗としてマークする

        Args:
            video_id: 動画ID

        Returns:
            成功したかどうか
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE song_queue
                SET status = 'failed', processed_at = ?
                WHERE video_id = ?
            """,
                (datetime.now(), video_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_song(self, video_id: str) -> bool:
        """
        曲をキューから削除する

        Args:
            video_id: 動画ID

        Returns:
            成功したかどうか
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM song_queue WHERE video_id = ?
            """,
                (video_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_counts(self) -> dict[str, int]:
        """
        ステータス別の件数を取得

        Returns:
            {'pending': n, 'processed': n, 'failed': n, 'total': n}
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM song_queue
                GROUP BY status
            """
            )
            counts = {"pending": 0, "processed": 0, "failed": 0, "total": 0}
            for row in cursor.fetchall():
                counts[row[0]] = row[1]
                counts["total"] += row[1]
            return counts

    def reset_failed(self) -> int:
        """
        失敗した曲を未処理に戻す

        Returns:
            更新した件数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE song_queue
                SET status = 'pending', processed_at = NULL
                WHERE status = 'failed'
            """
            )
            conn.commit()
            return cursor.rowcount
