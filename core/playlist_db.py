"""
作成済みプレイリストのMySQL管理モジュール

プレイリストのヘッダー情報と曲明細を管理する。
"""

from datetime import datetime
from sqlalchemy import select, delete

from core.database import get_session
from core.models import PlaylistHeader, PlaylistItem, PlaylistComment


def save_playlist_result(
    playlist_id: str,
    playlist_name: str,
    playlist_url: str,
    creator_sub: str,
    items: list[dict],
    header_comment: str | None = None,
) -> bool:
    """
    プレイリストのヘッダーと明細を保存する

    Args:
        playlist_id: YouTubeプレイリストID
        playlist_name: プレイリスト名
        playlist_url: プレイリストURL
        creator_sub: 作成者のユーザーSub
        items: [{"seq": int, "song_id": str, "cosine_distance": float}, ...]
    """
    if not playlist_id or not playlist_name or not playlist_url or not creator_sub:
        return False

    with get_session() as session:
        header = session.execute(
            select(PlaylistHeader).where(PlaylistHeader.playlist_id == playlist_id)
        ).scalar_one_or_none()

        if header:
            header.playlist_name = playlist_name
            header.playlist_url = playlist_url
            header.creator_sub = creator_sub
            if header_comment is not None:
                header.header_comment = header_comment
            header.created_at = datetime.now()
            session.execute(
                delete(PlaylistItem).where(PlaylistItem.playlist_id == playlist_id)
            )
        else:
            header = PlaylistHeader(
                playlist_id=playlist_id,
                playlist_name=playlist_name,
                playlist_url=playlist_url,
                creator_sub=creator_sub,
                header_comment=header_comment,
                created_at=datetime.now(),
            )
            session.add(header)

        for item in items:
            session.add(
                PlaylistItem(
                    playlist_id=playlist_id,
                    seq=item["seq"],
                    song_id=item["song_id"],
                    cosine_distance=item["cosine_distance"],
                )
            )

    return True


def list_playlist_headers(
    creator_sub: str | None = None,
    keyword: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    プレイリストのヘッダー一覧を取得する

    Args:
        creator_sub: 作成者のユーザーSubでフィルタ
        keyword: プレイリスト名またはIDの部分一致
        limit: 取得件数上限

    Returns:
        プレイリストヘッダーの辞書リスト
    """
    with get_session() as session:
        stmt = select(PlaylistHeader).order_by(PlaylistHeader.created_at.desc())
        if creator_sub:
            stmt = stmt.where(PlaylistHeader.creator_sub == creator_sub)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                (PlaylistHeader.playlist_name.like(like))
                | (PlaylistHeader.playlist_id.like(like))
            )
        stmt = stmt.limit(limit)
        rows = list(session.execute(stmt).scalars().all())
        return [
            {
                "playlist_id": row.playlist_id,
                "playlist_name": row.playlist_name,
                "playlist_url": row.playlist_url,
                "creator_sub": row.creator_sub,
                "header_comment": row.header_comment or "",
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def add_playlist_comment(
    playlist_id: str,
    user_sub: str,
    comment: str,
) -> bool:
    """
    プレイリストコメントを追加する

    Args:
        playlist_id: YouTubeプレイリストID
        user_sub: 投稿ユーザーのSub
        comment: コメント本文
    """
    if not playlist_id or not user_sub or not comment or not comment.strip():
        return False

    with get_session() as session:
        session.add(
            PlaylistComment(
                playlist_id=playlist_id,
                user_sub=user_sub,
                comment=comment.strip(),
                created_at=datetime.now(),
            )
        )

    return True


def list_playlist_comments(
    playlist_id: str,
    limit: int = 200,
) -> list[dict]:
    """
    プレイリストコメント一覧を取得する

    Args:
        playlist_id: YouTubeプレイリストID
        limit: 取得件数上限

    Returns:
        コメントの辞書リスト
    """
    if not playlist_id:
        return []

    with get_session() as session:
        stmt = (
            select(PlaylistComment)
            .where(PlaylistComment.playlist_id == playlist_id)
            .order_by(PlaylistComment.created_at.asc())
            .limit(limit)
        )
        rows = list(session.execute(stmt).scalars().all())
        return [
            {
                "id": row.id,
                "playlist_id": row.playlist_id,
                "user_sub": row.user_sub,
                "comment": row.comment,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def get_playlist_items(playlist_id: str) -> list[dict]:
    """
    プレイリストの曲明細を取得する

    Args:
        playlist_id: YouTubeプレイリストID

    Returns:
        曲明細の辞書リスト
    """
    if not playlist_id:
        return []

    with get_session() as session:
        stmt = (
            select(PlaylistItem)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.seq)
        )
        rows = list(session.execute(stmt).scalars().all())
        return [
            {
                "seq": row.seq,
                "song_id": row.song_id,
                "cosine_distance": row.cosine_distance,
            }
            for row in rows
        ]


def get_top_selected_songs(limit: int = 30) -> list[dict]:
    """
    プレイリストで最も選ばれている曲のTOP N を取得する

    Args:
        limit: 取得件数（デフォルト: 30）

    Returns:
        [{"song_id": str, "count": int}, ...]
    """
    from sqlalchemy import func

    with get_session() as session:
        stmt = (
            select(PlaylistItem.song_id, func.count(PlaylistItem.song_id).label("count"))
            .group_by(PlaylistItem.song_id)
            .order_by(func.count(PlaylistItem.song_id).desc())
            .limit(limit)
        )
        rows = list(session.execute(stmt).all())
        return [{"song_id": row[0], "count": row[1]} for row in rows]


def get_top_selected_artists(limit: int = 30) -> list[dict]:
    """
    プレイリストで最も選ばれているアーティストのTOP N を取得する
    
    空文字列のアーティスト名は除外されます（アーティスト情報が不明な曲を除くため）

    Args:
        limit: 取得件数（デフォルト: 30）

    Returns:
        [{"artist_name": str, "count": int}, ...]
    """
    from sqlalchemy import func
    from core.models import Song

    with get_session() as session:
        # PlaylistItem と Song を結合してアーティスト名を取得
        stmt = (
            select(Song.artist_name, func.count(PlaylistItem.song_id).label("count"))
            .join(Song, PlaylistItem.song_id == Song.song_id)
            .where(Song.artist_name != "")
            .group_by(Song.artist_name)
            .order_by(func.count(PlaylistItem.song_id).desc())
            .limit(limit)
        )
        rows = list(session.execute(stmt).all())
        return [{"artist_name": row[0], "count": row[1]} for row in rows]
