"""
作成済みプレイリストのMySQL管理モジュール

プレイリストのヘッダー情報と曲明細を管理する。
"""

from datetime import datetime
from sqlalchemy import select, delete

from core.database import get_session
from core.models import PlaylistHeader, PlaylistItem


def save_playlist_result(
    playlist_id: str,
    playlist_name: str,
    playlist_url: str,
    creator_sub: str,
    items: list[dict],
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
