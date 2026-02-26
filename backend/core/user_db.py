"""
ユーザー情報（Subとメールアドレス）の管理モジュール
"""

from datetime import datetime
from sqlalchemy import select

from core.database import get_session
from core.models import UserIdentity


def upsert_user_identity(user_sub: str, email: str | None) -> None:
    """
    ユーザーSubとメールアドレスを保存/更新する

    Args:
        user_sub: GoogleのSub
        email: ログイン時のメールアドレス
    """
    if not user_sub:
        return

    email_value = email or ""
    with get_session() as session:
        existing = session.execute(
            select(UserIdentity).where(UserIdentity.user_sub == user_sub)
        ).scalar_one_or_none()

        if existing:
            existing.email = email_value
            existing.updated_at = datetime.now()
        else:
            session.add(
                UserIdentity(
                    user_sub=user_sub,
                    email=email_value,
                    updated_at=datetime.now(),
                )
            )


def get_emails_by_subs(user_subs: list[str]) -> dict[str, str]:
    """
    複数のSubからメールアドレスを取得する

    Args:
        user_subs: Subのリスト

    Returns:
        {sub: email} の辞書
    """
    if not user_subs:
        return {}

    with get_session() as session:
        rows = list(
            session.execute(
                select(UserIdentity).where(UserIdentity.user_sub.in_(user_subs))
            )
            .scalars()
            .all()
        )
        return {row.user_sub: row.email for row in rows}


def get_display_names_by_subs(user_subs: list[str]) -> dict[str, str]:
    """
    複数のSubから表示名（エイリアスまたはメールアドレス）を取得する

    Args:
        user_subs: Subのリスト

    Returns:
        {sub: display_name} の辞書（エイリアスがあればエイリアス、なければメールアドレス）
    """
    if not user_subs:
        return {}

    with get_session() as session:
        rows = list(
            session.execute(
                select(UserIdentity).where(UserIdentity.user_sub.in_(user_subs))
            )
            .scalars()
            .all()
        )
        return {
            row.user_sub: row.alias if row.alias else row.email
            for row in rows
        }


def get_user_alias(user_sub: str) -> str:
    """
    ユーザーのエイリアスを取得する

    Args:
        user_sub: GoogleのSub

    Returns:
        エイリアス（設定されていない場合は空文字列）
    """
    if not user_sub:
        return ""

    with get_session() as session:
        existing = session.execute(
            select(UserIdentity).where(UserIdentity.user_sub == user_sub)
        ).scalar_one_or_none()

        return existing.alias if existing and existing.alias else ""


def update_user_alias(user_sub: str, alias: str) -> bool:
    """
    ユーザーのエイリアスを更新する
    
    注意: ユーザーが存在しない場合は新規作成されます（emailは空文字列）

    Args:
        user_sub: GoogleのSub
        alias: 新しいエイリアス

    Returns:
        更新が成功したかどうか
    """
    if not user_sub:
        return False

    try:
        with get_session() as session:
            existing = session.execute(
                select(UserIdentity).where(UserIdentity.user_sub == user_sub)
            ).scalar_one_or_none()

            if existing:
                existing.alias = alias
                existing.updated_at = datetime.now()
                return True
            else:
                # ユーザーが存在しない場合は作成
                # 通常はログイン時に upsert_user_identity で作成されるが、
                # エッジケースに備えて作成できるようにする
                session.add(
                    UserIdentity(
                        user_sub=user_sub,
                        email="",
                        alias=alias,
                        updated_at=datetime.now(),
                    )
                )
                return True
    except Exception as e:
        # データベースエラーが発生した場合はログに記録して False を返す
        import logging
        logging.error(f"Failed to update user alias for {user_sub}: {e}")
        return False
