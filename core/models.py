"""
SQLAlchemy モデル定義

MySQLデータベースのテーブル構造を定義
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """すべてのモデルの基底クラス"""

    pass


class SongQueue(Base):
    """YouTube曲登録キューテーブル"""

    __tablename__ = "song_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(11), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    artist_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_dir: Mapped[str] = mapped_column(
        String(100), nullable=False, default="youtube", server_default="youtube"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # インデックス定義
    __table_args__ = (
        Index("idx_status", "status"),
        Index("idx_registered_at", "registered_at"),
    )

    def __repr__(self) -> str:
        return f"<SongQueue(id={self.id}, video_id='{self.video_id}', status='{self.status}')>"


class YouTubeChannel(Base):
    """YouTubeチャンネル管理テーブル"""

    __tablename__ = "youtube_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    output_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # インデックス定義
    __table_args__ = (
        Index("idx_channel_id", "channel_id"),
        Index("idx_registered_at", "registered_at"),
    )

    def __repr__(self) -> str:
        return f"<YouTubeChannel(id={self.id}, channel_id='{self.channel_id}', channel_name='{self.channel_name}')>"
