#!/usr/bin/env python3
"""
ユーザーごとのYouTube Music OAuth認証情報テーブルを追加するマイグレーションスクリプト

使い方:
    uv run python add_user_ytmusic_auth_table.py
"""

from core.database import engine, init_database
from core.models import Base, UserYouTubeMusicAuth


def main():
    """
    user_ytmusic_auth テーブルを作成
    """
    print("=" * 50)
    print("YouTube Music OAuth認証テーブル追加マイグレーション")
    print("=" * 50)
    print()

    try:
        # UserYouTubeMusicAuth テーブルのみを作成
        print("user_ytmusic_auth テーブルを作成中...")
        UserYouTubeMusicAuth.__table__.create(bind=engine, checkfirst=True)
        print("✅ テーブルの作成が完了しました")
        print()
        print("テーブル: user_ytmusic_auth")
        print("  - id (PRIMARY KEY)")
        print("  - user_sub (FOREIGN KEY -> user_identities.user_sub, UNIQUE)")
        print("  - oauth_json (TEXT)")
        print("  - created_at (DATETIME)")
        print("  - updated_at (DATETIME)")
        print()
        print("マイグレーション完了！")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
