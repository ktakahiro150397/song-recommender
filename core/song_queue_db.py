"""
YouTube曲登録キュー管理用のMySQLデータベース操作モジュール

Streamlitで登録されたYouTube動画URLを保存し、
後からバッチ処理でダウンロード・DB登録を行う
"""

import re
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update, delete, func
from core.database import get_session, init_database
from core.models import SongQueue


class SongQueueDB:
    """YouTube曲登録キューを管理するクラス"""

    def __init__(self):
        """データベースとテーブルを初期化"""
        init_database()

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
            with get_session() as session:
                # 既存チェック
                existing = session.execute(
                    select(SongQueue).where(SongQueue.video_id == video_id)
                ).scalar_one_or_none()

                if existing:
                    return False, f"既に登録済みです: {video_id}", video_id

                # 新規登録
                song = SongQueue(
                    video_id=video_id,
                    url=url,
                    title=title,
                    status="pending",
                    registered_at=datetime.now(),
                )
                session.add(song)
                session.commit()
                return True, f"登録しました: {video_id}", video_id

        except Exception as e:
            return False, f"登録エラー: {str(e)}", video_id

    def get_pending_songs(self) -> list[dict]:
        """
        未処理の曲リストを取得

        Returns:
            未処理の曲情報のリスト
        """
        with get_session() as session:
            songs = (
                session.execute(
                    select(SongQueue)
                    .where(SongQueue.status == "pending")
                    .order_by(SongQueue.registered_at.asc())
                )
                .scalars()
                .all()
            )

            return [
                {
                    "id": song.id,
                    "video_id": song.video_id,
                    "url": song.url,
                    "title": song.title,
                    "status": song.status,
                    "registered_at": (
                        song.registered_at.isoformat() if song.registered_at else None
                    ),
                }
                for song in songs
            ]

    def get_all_songs(self, limit: int = 100) -> list[dict]:
        """
        全ての曲リストを取得

        Args:
            limit: 取得件数の上限

        Returns:
            曲情報のリスト
        """
        with get_session() as session:
            songs = (
                session.execute(
                    select(SongQueue)
                    .order_by(SongQueue.registered_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )

            return [
                {
                    "id": song.id,
                    "video_id": song.video_id,
                    "url": song.url,
                    "title": song.title,
                    "status": song.status,
                    "registered_at": (
                        song.registered_at.isoformat() if song.registered_at else None
                    ),
                    "processed_at": (
                        song.processed_at.isoformat() if song.processed_at else None
                    ),
                }
                for song in songs
            ]

    def mark_as_processed(self, video_id: str) -> bool:
        """
        曲を処理済みにマークする

        Args:
            video_id: 動画ID

        Returns:
            成功したかどうか
        """
        with get_session() as session:
            result = session.execute(
                update(SongQueue)
                .where(SongQueue.video_id == video_id)
                .values(status="processed", processed_at=datetime.now())
            )
            session.commit()
            return result.rowcount > 0

    def mark_as_failed(self, video_id: str) -> bool:
        """
        曲を失敗としてマークする

        Args:
            video_id: 動画ID

        Returns:
            成功したかどうか
        """
        with get_session() as session:
            result = session.execute(
                update(SongQueue)
                .where(SongQueue.video_id == video_id)
                .values(status="failed", processed_at=datetime.now())
            )
            session.commit()
            return result.rowcount > 0

    def delete_song(self, video_id: str) -> bool:
        """
        曲をキューから削除する

        Args:
            video_id: 動画ID

        Returns:
            成功したかどうか
        """
        with get_session() as session:
            result = session.execute(
                delete(SongQueue).where(SongQueue.video_id == video_id)
            )
            session.commit()
            return result.rowcount > 0

    def get_counts(self) -> dict[str, int]:
        """
        ステータス別の件数を取得

        Returns:
            {'pending': n, 'processed': n, 'failed': n, 'total': n}
        """
        with get_session() as session:
            results = session.execute(
                select(SongQueue.status, func.count(SongQueue.id)).group_by(
                    SongQueue.status
                )
            ).all()

            counts = {"pending": 0, "processed": 0, "failed": 0, "total": 0}
            for status, count in results:
                counts[status] = count
                counts["total"] += count

            return counts

    def reset_failed(self) -> int:
        """
        失敗した曲を未処理に戻す

        Returns:
            更新した件数
        """
        with get_session() as session:
            result = session.execute(
                update(SongQueue)
                .where(SongQueue.status == "failed")
                .values(status="pending", processed_at=None)
            )
            session.commit()
            return result.rowcount
