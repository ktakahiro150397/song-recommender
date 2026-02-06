#!/usr/bin/env python3
"""
プレイリストコメントテーブルにis_deleted列を追加するマイグレーションスクリプト
"""

from core.database import get_session
from sqlalchemy import text


def add_is_deleted_column():
    """playlist_commentsテーブルにis_deleted列を追加"""
    with get_session() as session:
        # まず列が存在するか確認
        check_query = text("""
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'playlist_comments'
            AND COLUMN_NAME = 'is_deleted'
        """)
        result = session.execute(check_query).scalar()

        if result == 0:
            # 列が存在しない場合のみ追加
            alter_query = text("""
                ALTER TABLE playlist_comments
                ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0
            """)
            session.execute(alter_query)
            print("✅ is_deleted列を追加しました")
        else:
            print("ℹ️  is_deleted列は既に存在します")


if __name__ == "__main__":
    print("プレイリストコメントテーブルのマイグレーションを開始します...")
    add_is_deleted_column()
    print("マイグレーション完了")
