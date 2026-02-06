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
