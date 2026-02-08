"""
ユーザーごとのYouTube Music OAuth認証管理モジュール
"""

import json
from datetime import datetime
from sqlalchemy import select

from core.database import get_session
from core.models import UserYouTubeMusicAuth


def save_user_oauth(user_sub: str, oauth_json_str: str) -> bool:
    """
    ユーザーのOAuth認証情報を保存/更新する

    Args:
        user_sub: GoogleのSub
        oauth_json_str: OAuth認証情報（JSON文字列）

    Returns:
        成功した場合True
    """
    if not user_sub or not oauth_json_str:
        return False

    try:
        # JSON形式が正しいか検証
        json.loads(oauth_json_str)
    except json.JSONDecodeError:
        return False

    try:
        with get_session() as session:
            existing = session.execute(
                select(UserYouTubeMusicAuth).where(
                    UserYouTubeMusicAuth.user_sub == user_sub
                )
            ).scalar_one_or_none()

            if existing:
                existing.oauth_json = oauth_json_str
                existing.updated_at = datetime.now()
            else:
                session.add(
                    UserYouTubeMusicAuth(
                        user_sub=user_sub,
                        oauth_json=oauth_json_str,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                )
            return True
    except Exception as e:
        import logging

        logging.error(f"Failed to save OAuth for user {user_sub}: {e}")
        return False


def get_user_oauth(user_sub: str) -> dict | None:
    """
    ユーザーのOAuth認証情報を取得する

    Args:
        user_sub: GoogleのSub

    Returns:
        OAuth認証情報（辞書形式）、存在しない場合はNone
    """
    if not user_sub:
        return None

    try:
        with get_session() as session:
            auth = session.execute(
                select(UserYouTubeMusicAuth).where(
                    UserYouTubeMusicAuth.user_sub == user_sub
                )
            ).scalar_one_or_none()

            if auth:
                return json.loads(auth.oauth_json)
            return None
    except Exception as e:
        import logging

        logging.error(f"Failed to get OAuth for user {user_sub}: {e}")
        return None


def delete_user_oauth(user_sub: str) -> bool:
    """
    ユーザーのOAuth認証情報を削除する

    Args:
        user_sub: GoogleのSub

    Returns:
        成功した場合True
    """
    if not user_sub:
        return False

    try:
        with get_session() as session:
            auth = session.execute(
                select(UserYouTubeMusicAuth).where(
                    UserYouTubeMusicAuth.user_sub == user_sub
                )
            ).scalar_one_or_none()

            if auth:
                session.delete(auth)
                return True
            return False
    except Exception as e:
        import logging

        logging.error(f"Failed to delete OAuth for user {user_sub}: {e}")
        return False


def has_user_oauth(user_sub: str) -> bool:
    """
    ユーザーがOAuth認証情報を持っているか確認する

    Args:
        user_sub: GoogleのSub

    Returns:
        認証情報が存在する場合True
    """
    if not user_sub:
        return False

    try:
        with get_session() as session:
            auth = session.execute(
                select(UserYouTubeMusicAuth).where(
                    UserYouTubeMusicAuth.user_sub == user_sub
                )
            ).scalar_one_or_none()

            return auth is not None
    except Exception:
        return False
