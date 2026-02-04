"""
MySQL データベース接続管理モジュール

SQLAlchemy 2.0を使用してMySQL接続を管理
"""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()


# データベース接続URL
def get_database_url() -> str:
    """MySQL接続URLを取得"""
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "song_recommender")
    user = os.getenv("MYSQL_USER", "app_user")
    password = os.getenv("MYSQL_PASSWORD", "app_password")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


# エンジン作成（コネクションプール付き）
engine = create_engine(
    get_database_url(),
    poolclass=QueuePool,
    pool_size=5,  # 通常時の接続数
    max_overflow=10,  # ピーク時の追加接続数
    pool_pre_ping=True,  # 接続前に生存確認
    pool_recycle=3600,  # 1時間で接続をリサイクル
    echo=False,  # SQLログを出力しない（デバッグ時はTrue）
)

# セッションファクトリ
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Session:
    """
    データベースセッションを取得するコンテキストマネージャ

    使用例:
        with get_session() as session:
            song = session.query(SongQueue).filter_by(id=1).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database():
    """
    データベースとテーブルを初期化

    注意: このメソッドはmodels.pyのBaseをインポートしてから呼び出す必要がある
    """
    from core.models import Base

    Base.metadata.create_all(bind=engine)
