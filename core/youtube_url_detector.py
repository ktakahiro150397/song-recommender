"""
YouTube URLの種類を自動判別するモジュール
"""

import re
from urllib.parse import urlparse
from typing import Literal, Tuple


URLType = Literal["channel", "video", "unknown"]


class YouTubeURLDetector:
    """YouTube URLの種類を自動判別するクラス"""

    # チャンネルURL判定パターン
    CHANNEL_PATTERNS = [
        r"/channel/UC[a-zA-Z0-9_-]+",
    ]

    # 動画URL判定パターン
    VIDEO_PATTERNS = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]

    @classmethod
    def detect(cls, url: str) -> Tuple[URLType, str]:
        """
        URLの種類を判別

        Args:
            url: 判別対象のURL

        Returns:
            (URLタイプ, エラーメッセージ)
        """
        url = url.strip()

        if not url:
            return "unknown", "URLが入力されていません"

        try:
            parsed = urlparse(url)

            # YouTubeドメインチェック
            valid_domains = [
                "www.youtube.com",
                "youtube.com",
                "m.youtube.com",
                "music.youtube.com",
                "youtu.be",
            ]

            # ドメインチェック（動画ID直接入力の場合はスキップ）
            if parsed.netloc and parsed.netloc not in valid_domains:
                return "unknown", "YouTubeのURLを入力してください"

            # チャンネル判定
            for pattern in cls.CHANNEL_PATTERNS:
                if re.search(pattern, url):
                    return "channel", ""

            # 動画判定
            for pattern in cls.VIDEO_PATTERNS:
                if re.search(pattern, url):
                    return "video", ""

            # 動画ID直接入力（11文字）
            if re.match(r"^[a-zA-Z0-9_-]{11}$", url):
                return "video", ""

            return (
                "unknown",
                "未対応のURL形式です。チャンネルURL（/channel/UC...）または動画URL（watch?v=...）を入力してください",
            )

        except Exception as e:
            return "unknown", f"URL解析エラー: {str(e)}"
