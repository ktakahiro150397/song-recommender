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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS youtube_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    channel_id TEXT NOT NULL,
                    channel_name TEXT,
                    thumbnail_url TEXT,
                    registered_at TIMESTAMP NOT NULL
                )
            """
            )
            # インデックスを作成
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_registered_at 
                ON youtube_channels(registered_at DESC)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_channel_id 
                ON youtube_channels(channel_id)
            """
            )
            conn.commit()

    @staticmethod
    def extract_channel_id(url: str) -> tuple[bool, str, str]:
        """
        YouTubeのURLからチャンネルIDを抽出する
        ※ /channel/UCxxxxx 形式のみ受け付けます

        Args:
            url: YouTubeチャンネルURL

        Returns:
            (成功/失敗, チャンネルID, エラーメッセージ) のタプル
        """
        try:
            parsed = urlparse(url)

            # スキームチェック
            if parsed.scheme not in ["http", "https"]:
                return False, "", "URLは http または https で始まる必要があります"

            # ドメインチェック
            valid_domains = [
                "www.youtube.com",
                "youtube.com",
                "m.youtube.com",
                "music.youtube.com",
            ]

            if parsed.netloc not in valid_domains:
                return (
                    False,
                    "",
                    f"YouTubeのURLを入力してください (有効なドメイン: {', '.join(valid_domains)})",
                )

            # パスからチャンネルIDを抽出（/channel/UCxxxxx 形式のみ）
            path = parsed.path.rstrip("/")

            # /channel/UCxxxxx 形式のみ受け付け
            if path.startswith("/channel/UC"):
                channel_id = path.replace("/channel/", "")
                if channel_id:
                    return True, channel_id, ""

            return (
                False,
                "",
                "チャンネルURLの形式が正しくありません。https://music.youtube.com/channel/UCxxxxx の形式で入力してください",
            )

        except Exception as e:
            return False, "", f"URL解析エラー: {str(e)}"

    @staticmethod
    def validate_youtube_url(url: str) -> tuple[bool, str]:
        """
        YouTubeのURLかどうかを検証する（後方互換性のため残す）

        Args:
            url: 検証するURL

        Returns:
            (検証結果, エラーメッセージ) のタプル
        """
        success, channel_id, error_msg = ChannelDB.extract_channel_id(url)
        return success, error_msg

    def add_channel(self, url: str, ytmusic=None) -> tuple[bool, str, Optional[str]]:
        """
        チャンネルURLを登録する

        Args:
            url: YouTubeチャンネルのURL
            ytmusic: YTMusicインスタンス（サムネイル・チャンネル名取得用、Noneの場合は取得なし）

        Returns:
            (成功/失敗, メッセージ, サムネイルURL) のタプル
        """
        # チャンネルIDを抽出
        success, channel_id, error_msg = self.extract_channel_id(url)
        if not success:
            return False, error_msg, None

        # サムネイルURLとチャンネル名を取得（YTMusic APIを使用）
        thumbnail_url = None
        channel_name = None
        if ytmusic is not None:
            try:
                # /channel/UCxxxxx 形式の場合のみAPI呼び出し
                if channel_id.startswith("UC"):
                    artist_info = ytmusic.get_artist(channel_id)
                    if artist_info:
                        # サムネイル取得
                        if (
                            "thumbnails" in artist_info
                            and len(artist_info["thumbnails"]) > 0
                        ):
                            thumbnail_url = artist_info["thumbnails"][0]["url"]
                        # チャンネル名取得
                        if "name" in artist_info:
                            channel_name = artist_info["name"]
            except Exception as e:
                # サムネイル・チャンネル名取得に失敗しても登録は続行
                print(f"サムネイル・チャンネル名取得エラー (続行します): {str(e)}")

        # 登録
        try:
            with sqlite3.connect(self.db_path) as conn:
                registered_at = datetime.now().isoformat()
                conn.execute(
                    "INSERT INTO youtube_channels (url, channel_id, channel_name, thumbnail_url, registered_at) VALUES (?, ?, ?, ?, ?)",
                    (url, channel_id, channel_name, thumbnail_url, registered_at),
                )
                conn.commit()
                return (
                    True,
                    f"チャンネルURLを登録しました (ID: {channel_id})",
                    thumbnail_url,
                )

        except sqlite3.IntegrityError:
            return False, "このURLは既に登録されています", None
        except Exception as e:
            return False, f"登録エラー: {str(e)}", None

    def get_all_channels(self) -> list[dict]:
        """
        登録されている全チャンネルを取得する（新しい順）

        Returns:
            チャンネル情報のリスト
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, url, channel_id, channel_name, thumbnail_url, registered_at 
                FROM youtube_channels 
                ORDER BY registered_at DESC
            """
            )
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
                    "DELETE FROM youtube_channels WHERE id = ?", (channel_id,)
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
                "SELECT COUNT(*) FROM youtube_channels WHERE url = ?", (url,)
            )
            return cursor.fetchone()[0] > 0

    def update_channel_name(self, channel_id: int, new_name: str) -> tuple[bool, str]:
        """
        チャンネル名（アーティスト名）を更新する

        Args:
            channel_id: 更新するチャンネルのID
            new_name: 新しいチャンネル名

        Returns:
            (成功/失敗, メッセージ) のタプル
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE youtube_channels SET channel_name = ? WHERE id = ?",
                    (new_name, channel_id),
                )
                conn.commit()

                if cursor.rowcount > 0:
                    return True, "アーティスト名を更新しました"
                else:
                    return False, "指定されたチャンネルが見つかりません"

        except Exception as e:
            return False, f"更新エラー: {str(e)}"
