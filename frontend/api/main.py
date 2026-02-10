from __future__ import annotations

from typing import Generic, Optional, TypeVar
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from core import playlist_db, song_metadata_db
from core.channel_db import ChannelDB
from core.database import get_session
from core.models import PlaylistHeader as PlaylistHeaderModel, ProcessedCollection
from core.song_queue_db import SongQueueDB
from core.user_db import get_display_names_by_subs

app = FastAPI(
    title="Song Recommender API",
    version="0.1.0",
    description="Operational endpoints backing the Next.js dashboard",
)

song_queue_db_client = SongQueueDB()
channel_db_client = ChannelDB()

DEFAULT_SONG_LIMIT = 200
MAX_SONG_LIMIT = 1000
DEFAULT_PLAYLIST_LIMIT = 20
MAX_PLAYLIST_LIMIT = 100
STATS_TOP_LIMIT = 10


class ResponseMeta(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None


class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, object]] = None


T = TypeVar("T")


class ResponseEnvelope(GenericModel, Generic[T]):
    data: T
    error: Optional[ApiError] = None
    meta: Optional[ResponseMeta] = None


class QueueCounts(BaseModel):
    pending: int
    processed: int
    failed: int
    total: int


class StatsOverview(BaseModel):
    total_songs: int
    total_channels: int
    queue_counts: QueueCounts
    total_size_gb: float


class SongCount(BaseModel):
    song_id: str
    count: int


class ArtistCount(BaseModel):
    artist_name: str
    count: int


class StatsPlaylists(BaseModel):
    top_songs: list[SongCount]
    top_artists: list[ArtistCount]
    top_start_songs: list[SongCount]


class DbCollectionCounts(BaseModel):
    full: int
    balance: int
    minimal: int
    seg_mert: int
    seg_ast: int


class SongSummary(BaseModel):
    song_id: str
    song_title: str
    artist_name: str
    source_dir: str
    bpm: Optional[float] = None
    youtube_id: str
    file_extension: str
    file_size_mb: float
    registered_at: str
    excluded_from_search: bool


class PlaylistHeader(BaseModel):
    playlist_id: str
    playlist_name: str
    playlist_url: str
    creator_sub: str
    creator_display_name: str
    created_at: str
    header_comment: Optional[str] = None


class PlaylistItem(BaseModel):
    seq: int
    song_id: str
    cosine_distance: float
    source_dir: str


class PlaylistComment(BaseModel):
    id: int
    playlist_id: str
    user_sub: str
    display_name: str
    comment: str
    is_deleted: bool
    created_at: str


class PlaylistHistoryEntry(BaseModel):
    header: PlaylistHeader
    items: list[PlaylistItem]
    comments: list[PlaylistComment]


def build_envelope(
    data,
    total: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    return ResponseEnvelope(
        data=data,
        error=None,
        meta=ResponseMeta(
            total=total,
            limit=limit if limit is not None else total,
            offset=offset,
        ),
    )


def _convert_song_summary(song_id: str, metadata: dict) -> SongSummary:
    return SongSummary(
        song_id=song_id,
        song_title=metadata.get("song_title", ""),
        artist_name=metadata.get("artist_name", ""),
        source_dir=metadata.get("source_dir", ""),
        bpm=metadata.get("bpm"),
        youtube_id=metadata.get("youtube_id", ""),
        file_extension=metadata.get("file_extension", ""),
        file_size_mb=float(metadata.get("file_size_mb", 0.0)),
        registered_at=metadata.get("registered_at", ""),
        excluded_from_search=bool(metadata.get("excluded_from_search", False)),
    )


def _resolve_source_dir(song_id: str, songs_meta: dict[str, dict]) -> str:
    metadata = songs_meta.get(song_id)
    return metadata.get("source_dir", "") if metadata else ""


def _build_playlist_entries(headers: list[dict]) -> list[PlaylistHistoryEntry]:
    if not headers:
        return []

    playlist_ids = [header["playlist_id"] for header in headers]
    items_map = {pid: playlist_db.get_playlist_items(pid) for pid in playlist_ids}
    comments_map = {
        pid: playlist_db.list_playlist_comments(pid) for pid in playlist_ids
    }

    song_ids = sorted(
        {
            item["song_id"]
            for items in items_map.values()
            for item in items
            if item.get("song_id")
        }
    )
    songs_meta = song_metadata_db.get_songs_as_dict(song_ids) if song_ids else {}

    user_subs: set[str] = {header["creator_sub"] for header in headers}
    for comments in comments_map.values():
        for comment in comments:
            user_subs.add(comment["user_sub"])
    display_names = get_display_names_by_subs(list(user_subs)) if user_subs else {}

    entries: list[PlaylistHistoryEntry] = []
    for header in headers:
        playlist_id = header["playlist_id"]
        header_model = PlaylistHeader(
            playlist_id=playlist_id,
            playlist_name=header["playlist_name"],
            playlist_url=header["playlist_url"],
            creator_sub=header["creator_sub"],
            creator_display_name=display_names.get(
                header["creator_sub"], header["creator_sub"]
            ),
            created_at=header["created_at"],
            header_comment=header.get("header_comment") or None,
        )

        items = [
            PlaylistItem(
                seq=item["seq"],
                song_id=item["song_id"],
                cosine_distance=item["cosine_distance"],
                source_dir=_resolve_source_dir(item["song_id"], songs_meta),
            )
            for item in items_map.get(playlist_id, [])
        ]

        comments = [
            PlaylistComment(
                id=comment["id"],
                playlist_id=playlist_id,
                user_sub=comment["user_sub"],
                display_name=display_names.get(
                    comment["user_sub"], comment["user_sub"]
                ),
                comment=comment["comment"],
                is_deleted=comment["is_deleted"],
                created_at=comment["created_at"],
            )
            for comment in comments_map.get(playlist_id, [])
        ]

        entries.append(
            PlaylistHistoryEntry(
                header=header_model,
                items=items,
                comments=comments,
            )
        )

    return entries


def _get_playlist_header_by_id(playlist_id: str) -> Optional[dict]:
    with get_session() as session:
        header = session.execute(
            select(PlaylistHeaderModel)
            .where(PlaylistHeaderModel.playlist_id == playlist_id)
            .where(PlaylistHeaderModel.deleted_at.is_(None))
        ).scalar_one_or_none()

        if not header:
            return None

        return {
            "playlist_id": header.playlist_id,
            "playlist_name": header.playlist_name,
            "playlist_url": header.playlist_url,
            "creator_sub": header.creator_sub,
            "header_comment": header.header_comment or "",
            "created_at": header.created_at.isoformat(),
        }


def _load_collection_counts() -> DbCollectionCounts:
    with get_session() as session:
        rows = session.execute(
            select(
                ProcessedCollection.collection_name,
                func.count(ProcessedCollection.id),
            ).group_by(ProcessedCollection.collection_name)
        ).all()

    counts = {name: count for name, count in rows}
    return DbCollectionCounts(
        full=counts.get("full", 0),
        balance=counts.get("balance", 0),
        minimal=counts.get("minimal", 0),
        seg_mert=counts.get("seg_mert", 0),
        seg_ast=counts.get("seg_ast", 0),
    )


@app.get("/api/stats/overview", response_model=ResponseEnvelope[StatsOverview])
async def get_stats_overview():
    try:
        total_songs = song_metadata_db.count_songs()
        total_channels = channel_db_client.get_channel_count()
        queue_counts_raw = song_queue_db_client.get_counts()
        queue_counts = QueueCounts(
            pending=queue_counts_raw.get("pending", 0),
            processed=queue_counts_raw.get("processed", 0),
            failed=queue_counts_raw.get("failed", 0),
            total=queue_counts_raw.get(
                "total",
                queue_counts_raw.get("pending", 0)
                + queue_counts_raw.get("processed", 0)
                + queue_counts_raw.get("failed", 0),
            ),
        )
        total_size_gb = song_metadata_db.get_total_processed_data_size_gb()
        stats = StatsOverview(
            total_songs=total_songs,
            total_channels=total_channels,
            queue_counts=queue_counts,
            total_size_gb=round(total_size_gb, 3),
        )
        return build_envelope(stats)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500, detail="Database error while loading overview stats"
        ) from exc
    except Exception as exc:  # pragma: no cover - unexpected runtime failures
        raise HTTPException(
            status_code=500, detail="Failed to load overview stats"
        ) from exc


@app.get("/api/stats/playlists", response_model=ResponseEnvelope[StatsPlaylists])
async def get_stats_playlists():
    try:
        top_songs_raw = playlist_db.get_top_selected_songs(limit=STATS_TOP_LIMIT)
        top_artists_raw = playlist_db.get_top_selected_artists(limit=STATS_TOP_LIMIT)
        top_start_songs_raw = playlist_db.get_top_selected_start_songs(
            limit=STATS_TOP_LIMIT
        )
        stats = StatsPlaylists(
            top_songs=[SongCount(**entry) for entry in top_songs_raw],
            top_artists=[ArtistCount(**entry) for entry in top_artists_raw],
            top_start_songs=[SongCount(**entry) for entry in top_start_songs_raw],
        )
        return build_envelope(stats)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500, detail="Database error while loading playlist stats"
        ) from exc


@app.get(
    "/api/stats/db-collections", response_model=ResponseEnvelope[DbCollectionCounts]
)
async def get_db_collection_counts():
    try:
        counts = _load_collection_counts()
        total_collections = sum(counts.model_dump().values())
        return build_envelope(counts, total=total_collections)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500, detail="Database error while loading collection stats"
        ) from exc


@app.get(
    "/api/songs",
    response_model=ResponseEnvelope[list[SongSummary]],
)
async def list_songs(
    keyword: Optional[str] = Query(
        default=None,
        description="Filter by song title, artist name, or song_id",
    ),
    limit: int = Query(
        default=DEFAULT_SONG_LIMIT,
        ge=1,
        le=MAX_SONG_LIMIT,
        description="Maximum number of songs to return",
    ),
):
    try:
        if keyword and keyword.strip():
            records = song_metadata_db.search_by_keyword(keyword.strip(), limit=limit)
        else:
            records = song_metadata_db.list_all(limit=limit)

        songs = [
            _convert_song_summary(song_id, metadata) for song_id, metadata in records
        ]
        return build_envelope(songs, total=len(songs), limit=limit)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500, detail="Database error while loading songs"
        ) from exc


@app.get(
    "/api/playlists",
    response_model=ResponseEnvelope[list[PlaylistHistoryEntry]],
)
async def list_playlists(
    keyword: Optional[str] = Query(
        default=None,
        description="Filter by playlist id or name",
    ),
    limit: int = Query(
        default=DEFAULT_PLAYLIST_LIMIT,
        ge=1,
        le=MAX_PLAYLIST_LIMIT,
        description="Maximum number of playlist histories to return",
    ),
):
    try:
        headers = playlist_db.list_playlist_headers(
            keyword=keyword.strip() if keyword else None,
            limit=limit,
        )
        entries = _build_playlist_entries(headers)
        return build_envelope(entries, total=len(entries), limit=limit)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500, detail="Database error while loading playlists"
        ) from exc


@app.get(
    "/api/playlists/{playlist_id}",
    response_model=ResponseEnvelope[PlaylistHistoryEntry],
)
async def get_playlist_detail(playlist_id: str):
    try:
        header = _get_playlist_header_by_id(playlist_id)
        if not header:
            raise HTTPException(status_code=404, detail="Playlist not found")
        entries = _build_playlist_entries([header])
        if not entries:
            raise HTTPException(status_code=404, detail="Playlist not found")
        return build_envelope(entries[0])
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500, detail="Database error while loading playlist detail"
        ) from exc


@app.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
