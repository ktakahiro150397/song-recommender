"""
YouTubeチャンネルURL管理用のMySQLデータベース操作モジュール
"""

from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from sqlalchemy import select, update, delete, func
from core.database import get_session, init_database
from core.models import YouTubeChannel


class ChannelDB:
    """YouTubeチャンネルURLを管理するクラス"""

    def __init__(self):
        """データベースとテーブルを初期化"""
        init_database()

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
            with get_session() as session:
                # 既存チェック
                existing = session.execute(
                    select(YouTubeChannel).where(YouTubeChannel.url == url)
                ).scalar_one_or_none()

                if existing:
                    return False, "このURLは既に登録されています", None

                # 新規登録
                channel = YouTubeChannel(
                    url=url,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    thumbnail_url=thumbnail_url,
                    registered_at=datetime.now(),
                    output_count=0,
                )
                session.add(channel)
                session.commit()
                return (
                    True,
                    f"チャンネルURLを登録しました (ID: {channel_id})",
                    thumbnail_url,
                )

        except Exception as e:
            return False, f"登録エラー: {str(e)}", None

    def get_all_channels(self) -> list[dict]:
        """
        登録されている全チャンネルを取得する（新しい順）

        Returns:
            チャンネル情報のリスト
        """
        with get_session() as session:
            channels = (
                session.execute(
                    select(YouTubeChannel).order_by(YouTubeChannel.registered_at.desc())
                )
                .scalars()
                .all()
            )

            return [
                {
                    "id": channel.id,
                    "url": channel.url,
                    "channel_id": channel.channel_id,
                    "channel_name": channel.channel_name,
                    "thumbnail_url": channel.thumbnail_url,
                    "registered_at": (
                        channel.registered_at.isoformat()
                        if channel.registered_at
                        else None
                    ),
                    "output_count": channel.output_count,
                }
                for channel in channels
            ]

    def delete_channel(self, channel_id: int) -> tuple[bool, str]:
        """
        チャンネルを削除する

        Args:
            channel_id: 削除するチャンネルのID

        Returns:
            (成功/失敗, メッセージ) のタプル
        """
        try:
            with get_session() as session:
                result = session.execute(
                    delete(YouTubeChannel).where(YouTubeChannel.id == channel_id)
                )
                session.commit()

                if result.rowcount > 0:
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
        with get_session() as session:
            count = session.execute(select(func.count(YouTubeChannel.id))).scalar()
            return count or 0

    def channel_exists(self, url: str) -> bool:
        """
        指定されたURLが既に登録されているかチェックする

        Args:
            url: チェックするURL

        Returns:
            存在する場合True
        """
        with get_session() as session:
            count = session.execute(
                select(func.count(YouTubeChannel.id)).where(YouTubeChannel.url == url)
            ).scalar()
            return (count or 0) > 0

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
            with get_session() as session:
                result = session.execute(
                    update(YouTubeChannel)
                    .where(YouTubeChannel.id == channel_id)
                    .values(channel_name=new_name)
                )
                session.commit()

                if result.rowcount > 0:
                    return True, "アーティスト名を更新しました"
                else:
                    return False, "指定されたチャンネルが見つかりません"

        except Exception as e:
            return False, f"更新エラー: {str(e)}"

    def increment_output_count(self, channel_id: str) -> tuple[bool, str]:
        """
        DLスクリプト出力回数をインクリメントする

        Args:
            channel_id: チャンネルID (UCから始まるもの)

        Returns:
            (成功/失敗, メッセージ) のタプル
        """
        try:
            with get_session() as session:
                result = session.execute(
                    update(YouTubeChannel)
                    .where(YouTubeChannel.channel_id == channel_id)
                    .values(output_count=YouTubeChannel.output_count + 1)
                )
                session.commit()

                if result.rowcount > 0:
                    # 更新後のカウントを取得
                    channel = session.execute(
                        select(YouTubeChannel).where(
                            YouTubeChannel.channel_id == channel_id
                        )
                    ).scalar_one_or_none()

                    if channel:
                        return (
                            True,
                            f"出力回数を更新しました (現在: {channel.output_count}回目)",
                        )
                    return True, "出力回数を更新しました"
                else:
                    return False, "指定されたチャンネルが見つかりません"

        except Exception as e:
            return False, f"更新エラー: {str(e)}"

    def get_channel_by_id(self, channel_id: str) -> Optional[dict]:
        """
        チャンネルIDでチャンネル情報を取得する

        Args:
            channel_id: チャンネルID (UCから始まるもの)

        Returns:
            チャンネル情報（見つからない場合はNone）
        """
        with get_session() as session:
            channel = session.execute(
                select(YouTubeChannel).where(YouTubeChannel.channel_id == channel_id)
            ).scalar_one_or_none()

            if channel:
                return {
                    "id": channel.id,
                    "url": channel.url,
                    "channel_id": channel.channel_id,
                    "channel_name": channel.channel_name,
                    "thumbnail_url": channel.thumbnail_url,
                    "registered_at": (
                        channel.registered_at.isoformat()
                        if channel.registered_at
                        else None
                    ),
                    "output_count": channel.output_count,
                }
            return None

    def get_channels_with_zero_output(self, output_count: int = 0) -> list[dict]:
        """
        指定したoutput_countのチャンネルを取得する

        Args:
            output_count: 取得するoutput_countの値（デフォルト: 0）

        Returns:
            チャンネル情報のリスト
        """
        with get_session() as session:
            channels = (
                session.execute(
                    select(YouTubeChannel)
                    .where(YouTubeChannel.output_count == output_count)
                    .order_by(YouTubeChannel.registered_at.desc())
                )
                .scalars()
                .all()
            )

            return [
                {
                    "id": channel.id,
                    "url": channel.url,
                    "channel_id": channel.channel_id,
                    "channel_name": channel.channel_name,
                    "thumbnail_url": channel.thumbnail_url,
                    "registered_at": (
                        channel.registered_at.isoformat()
                        if channel.registered_at
                        else None
                    ),
                    "output_count": channel.output_count,
                }
                for channel in channels
            ]
