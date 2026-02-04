"""
YouTube URL統合登録モジュール
チャンネルと動画の両方に対応
"""

from typing import Tuple
from core.youtube_url_detector import YouTubeURLDetector
from core.channel_db import ChannelDB
from core.song_queue_db import SongQueueDB


class YouTubeRegistration:
    """YouTube URLの統合登録クラス"""

    def __init__(self):
        """初期化"""
        self.channel_db = ChannelDB()
        self.song_db = SongQueueDB()
        self.detector = YouTubeURLDetector()

    def register_url(self, url: str, ytmusic=None) -> Tuple[bool, str, str]:
        """
        URLを自動判別して登録

        Args:
            url: YouTubeのURL
            ytmusic: YTMusicインスタンス（チャンネル登録時のサムネイル取得用）

        Returns:
            (成功/失敗, メッセージ, URLタイプ)
        """
        # URLタイプを判別
        url_type, error_msg = self.detector.detect(url)

        if url_type == "unknown":
            return False, error_msg, "unknown"

        # チャンネル登録
        if url_type == "channel":
            success, message, thumbnail = self.channel_db.add_channel(
                url, ytmusic=ytmusic
            )
            return success, message, "channel"

        # 動画登録
        elif url_type == "video":
            success, message, video_id = self.song_db.add_song(url)
            return success, message, "video"

        return False, "不明なエラーが発生しました", "unknown"

    def register_urls_batch(
        self, urls: list[str], ytmusic=None, progress_callback=None
    ) -> dict:
        """
        複数URLを一括登録

        Args:
            urls: URLリスト
            ytmusic: YTMusicインスタンス
            progress_callback: 進捗コールバック関数 (current, total, url)

        Returns:
            登録結果の辞書
        """
        results = {
            "total": len(urls),
            "channel_success": 0,
            "channel_failed": 0,
            "video_success": 0,
            "video_failed": 0,
            "unknown": 0,
            "details": [],
        }

        for idx, url in enumerate(urls, 1):
            # 進捗コールバック
            if progress_callback:
                progress_callback(idx, len(urls), url)

            # 登録実行
            success, message, url_type = self.register_url(url, ytmusic=ytmusic)

            # 結果を集計
            if url_type == "channel":
                if success:
                    results["channel_success"] += 1
                else:
                    results["channel_failed"] += 1
            elif url_type == "video":
                if success:
                    results["video_success"] += 1
                else:
                    results["video_failed"] += 1
            else:
                results["unknown"] += 1

            # 詳細を追加
            results["details"].append(
                {"url": url, "success": success, "message": message, "type": url_type}
            )

        return results
