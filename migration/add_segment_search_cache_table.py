"""
Database migration script: add segment_search_cache table.

Usage:
    python add_segment_search_cache_table.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env
load_dotenv()


def get_database_url() -> str:
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "song_recommender")
    user = os.getenv("MYSQL_USER", "app_user")
    password = os.getenv("MYSQL_PASSWORD", "app_password")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


def add_segment_search_cache_table() -> None:
    engine = create_engine(get_database_url())

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT COUNT(*) as count
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = :database
                    AND TABLE_NAME = 'segment_search_cache'
                    """
                ),
                {"database": os.getenv("MYSQL_DATABASE", "song_recommender")},
            )
            count = result.scalar()

            if count and int(count) > 0:
                print("segment_search_cache table already exists")
                return

            print("Creating segment_search_cache table...")
            conn.execute(
                text(
                    """
                    CREATE TABLE segment_search_cache (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        collection_name VARCHAR(100) NOT NULL,
                        song_id VARCHAR(500) NOT NULL,
                        params_hash CHAR(64) NOT NULL,
                        results_json TEXT NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        UNIQUE KEY idx_segment_search_cache_unique (collection_name, song_id, params_hash),
                        KEY idx_segment_search_cache_updated (updated_at)
                    ) CHARACTER SET utf8mb4
                    """
                )
            )
            conn.commit()
            print("segment_search_cache table created")
    finally:
        engine.dispose()


if __name__ == "__main__":
    print("=== segment_search_cache migration ===")
    try:
        add_segment_search_cache_table()
        print("migration complete")
    except Exception as exc:
        print(f"migration failed: {exc}")
        raise
