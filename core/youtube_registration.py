"""
YouTube URL統合登録モジュール
チャンネル、動画、プレイリストに対応
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

    def extract_playlist_videos(self, playlist_url: str, ytmusic=None) -> Tuple[bool, str, list[str]]:
        """
        プレイリストから動画IDリストを抽出

        Args:
            playlist_url: プレイリストのURL
            ytmusic: YTMusicインスタンス

        Returns:
            (成功/失敗, メッセージ, 動画IDリスト)
        """
        playlist_id = self.detector.extract_playlist_id(playlist_url)
        if not playlist_id:
            return False, "プレイリストIDを抽出できませんでした", []

        # ytmusicが利用できない場合はNotImplemented
        if ytmusic is None:
            raise NotImplementedError("プレイリストからの動画抽出にはYTMusic APIが必要です")

        try:
            # プレイリストの情報を取得
            playlist_data = ytmusic.get_playlist(playlist_id, limit=None)
            
            video_ids = []
            if "tracks" in playlist_data and playlist_data["tracks"]:
                for track in playlist_data["tracks"]:
                    if track and "videoId" in track and track["videoId"]:
                        video_ids.append(track["videoId"])
            
            if not video_ids:
                return False, "プレイリストに動画が見つかりませんでした", []
            
            return True, f"プレイリストから{len(video_ids)}件の動画を抽出しました", video_ids
            
        except Exception as e:
            return False, f"プレイリスト取得エラー: {str(e)}", []

    def register_url(self, url: str, ytmusic=None) -> Tuple[bool, str, str]:
        """
        URLを自動判別して登録

        Args:
            url: YouTubeのURL
            ytmusic: YTMusicインスタンス（チャンネル登録時のサムネイル取得用、プレイリスト抽出用）

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

        # プレイリスト登録
        elif url_type == "playlist":
            try:
                success, message, video_ids = self.extract_playlist_videos(url, ytmusic=ytmusic)
                if not success:
                    return False, message, "playlist"
                
                # 各動画をキューに追加
                added_count = 0
                skipped_count = 0
                failed_count = 0
                
                for video_id in video_ids:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    success, msg, returned_video_id = self.song_db.add_song(video_url)
                    if success:
                        added_count += 1
                    elif returned_video_id and not success:
                        # If video_id is returned but not successful, it's likely a duplicate
                        skipped_count += 1
                    else:
                        failed_count += 1
                
                result_message = f"プレイリスト登録完了: {added_count}件追加"
                if skipped_count > 0:
                    result_message += f", {skipped_count}件スキップ（既存）"
                if failed_count > 0:
                    result_message += f", {failed_count}件失敗"
                
                return True, result_message, "playlist"
                
            except NotImplementedError as e:
                return False, str(e), "playlist"
            except Exception as e:
                return False, f"プレイリスト登録エラー: {str(e)}", "playlist"

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
            "playlist_success": 0,
            "playlist_failed": 0,
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
            elif url_type == "playlist":
                if success:
                    results["playlist_success"] += 1
                else:
                    results["playlist_failed"] += 1
            else:
                results["unknown"] += 1

            # 詳細を追加
            results["details"].append(
                {"url": url, "success": success, "message": message, "type": url_type}
            )

        return results
