"""
SQLAlchemy モデル定義

MySQLデータベースのテーブル構造を定義
"""

from datetime import datetime
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Text,
    Index,
    Float,
    Boolean,
    ForeignKey,
)
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
    artist_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    source_dir: Mapped[str] = mapped_column(String(100), nullable=False)
    youtube_id: Mapped[str] = mapped_column(
        String(11), nullable=False, default="", server_default=""
    )
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size_mb: Mapped[float] = mapped_column(Float, nullable=False)
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
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


class PlaylistHeader(Base):
    """作成済みプレイリストのヘッダー情報"""

    __tablename__ = "playlist_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    playlist_name: Mapped[str] = mapped_column(String(500), nullable=False)
    playlist_url: Mapped[str] = mapped_column(String(500), nullable=False)
    creator_sub: Mapped[str] = mapped_column(String(200), nullable=False)
    header_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )

    __table_args__ = (
        Index("idx_playlist_id", "playlist_id"),
        Index("idx_creator_sub", "creator_sub"),
        Index("idx_playlist_created_at", "created_at"),
        Index("idx_playlist_deleted_at", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<PlaylistHeader(playlist_id='{self.playlist_id}', playlist_name='{self.playlist_name}')>"


class PlaylistComment(Base):
    """プレイリストコメント（チャット形式）"""

    __tablename__ = "playlist_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[str] = mapped_column(
        String(200),
        ForeignKey("playlist_headers.playlist_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_sub: Mapped[str] = mapped_column(String(200), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    __table_args__ = (
        Index("idx_playlist_comment_playlist", "playlist_id", "created_at"),
        Index("idx_playlist_comment_user", "user_sub"),
    )

    def __repr__(self) -> str:
        return f"<PlaylistComment(playlist_id='{self.playlist_id}', user_sub='{self.user_sub}')>"


class PlaylistItem(Base):
    """作成済みプレイリストの曲明細"""

    __tablename__ = "playlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[str] = mapped_column(
        String(200),
        ForeignKey("playlist_headers.playlist_id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    song_id: Mapped[str] = mapped_column(String(500), nullable=False)
    cosine_distance: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("idx_playlist_seq", "playlist_id", "seq"),
        Index("idx_playlist_song_id", "song_id"),
    )

    def __repr__(self) -> str:
        return f"<PlaylistItem(playlist_id='{self.playlist_id}', seq={self.seq}, song_id='{self.song_id}')>"


class UserIdentity(Base):
    """ユーザーSubとメールアドレスの紐付け"""

    __tablename__ = "user_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_sub: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(
        String(320), nullable=False, default="", server_default=""
    )
    alias: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    __table_args__ = (
        Index("idx_user_sub", "user_sub"),
        Index("idx_user_email", "email"),
        Index("idx_user_updated_at", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<UserIdentity(user_sub='{self.user_sub}', email='{self.email}', alias='{self.alias}')>"
