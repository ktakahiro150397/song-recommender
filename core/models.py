"""
SQLAlchemy モデル定義

MySQLデータベースのテーブル構造を定義
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Index, Float, Boolean, ForeignKey
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


class Song(Base):
    """楽曲メタデータテーブル"""

    __tablename__ = "songs"

    # song_id はファイル名をベースにした一意なID
    song_id: Mapped[str] = mapped_column(String(500), primary_key=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    song_title: Mapped[str] = mapped_column(String(500), nullable=False)
    artist_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    source_dir: Mapped[str] = mapped_column(String(100), nullable=False)
    youtube_id: Mapped[str] = mapped_column(String(11), nullable=False, default="", server_default="")
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size_mb: Mapped[float] = mapped_column(Float, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    excluded_from_search: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    # インデックス定義
    __table_args__ = (
        Index("idx_song_title", "song_title"),
        Index("idx_artist_name", "artist_name"),
        Index("idx_source_dir", "source_dir"),
        Index("idx_youtube_id", "youtube_id"),
        Index("idx_registered_at", "registered_at"),
        Index("idx_excluded_from_search", "excluded_from_search"),
    )

    def __repr__(self) -> str:
        return f"<Song(song_id='{self.song_id}', song_title='{self.song_title}', artist_name='{self.artist_name}')>"


class ProcessedCollection(Base):
    """ベクトルDBコレクションごとの処理済み楽曲管理テーブル"""

    __tablename__ = "processed_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    song_id: Mapped[str] = mapped_column(
        String(500), ForeignKey("songs.song_id", ondelete="CASCADE"), nullable=False
    )
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    # インデックス定義
    __table_args__ = (
        Index("idx_song_collection", "song_id", "collection_name", unique=True),
        Index("idx_collection_name", "collection_name"),
        Index("idx_processed_at", "processed_at"),
    )

    def __repr__(self) -> str:
        return f"<ProcessedCollection(song_id='{self.song_id}', collection_name='{self.collection_name}')>"
