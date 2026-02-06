"""
データベース移行スクリプト: user_identities テーブルに alias カラムを追加

実行方法:
    python add_user_alias_column.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# .envファイルを読み込み
load_dotenv()


def get_database_url() -> str:
    """MySQL接続URLを取得"""
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "song_recommender")
    user = os.getenv("MYSQL_USER", "app_user")
    password = os.getenv("MYSQL_PASSWORD", "app_password")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


def add_alias_column():
    """user_identities テーブルに alias カラムを追加"""
    engine = create_engine(get_database_url())

    with engine.connect() as conn:
        # カラムが既に存在するかチェック
        result = conn.execute(
            text(
                """
                SELECT COUNT(*) as count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = :database
                AND TABLE_NAME = 'user_identities'
                AND COLUMN_NAME = 'alias'
                """
            ),
            {"database": os.getenv("MYSQL_DATABASE", "song_recommender")},
        )
        count = result.scalar()

        if count > 0:
            print("✓ alias カラムは既に存在します")
            return

        # カラムを追加
        print("alias カラムを追加中...")
        conn.execute(
            text(
                """
                ALTER TABLE user_identities
                ADD COLUMN alias VARCHAR(100) NOT NULL DEFAULT '' AFTER email
                """
            )
        )
        conn.commit()
        print("✓ alias カラムを追加しました")


if __name__ == "__main__":
    print("=== user_identities テーブル移行スクリプト ===")
    print("alias カラムを追加します...\n")

    try:
        add_alias_column()
        print("\n✓ 移行が完了しました")
    except Exception as e:
        print(f"\n✗ エラーが発生しました: {e}")
        raise
