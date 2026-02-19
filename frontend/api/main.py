from __future__ import annotations

import logging
import os
from collections import Counter
from typing import Generic, Optional, TypeVar

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from core import playlist_db, song_metadata_db
from core.channel_db import ChannelDB
from core.database import get_session
from core.models import PlaylistHeader as PlaylistHeaderModel, ProcessedCollection
from core.db_manager import SongVectorDB
from core.song_queue_db import SongQueueDB
from core.segment_search_cache import (
    build_params_hash,
    get_segment_search_cache,
    save_segment_search_cache,
)
from core.user_db import get_display_names_by_subs
from observability import configure_logging, get_request_id, setup_observability

configure_logging()
app = FastAPI(
    title="Song Recommender API",
    version="0.1.0",
    description="Operational endpoints backing the Next.js dashboard",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
setup_observability(app)

logger = logging.getLogger("song_rec_api")

song_queue_db_client = SongQueueDB()
channel_db_client = ChannelDB()

DEFAULT_SONG_LIMIT = 30
MAX_SONG_LIMIT = 1000
DEFAULT_PLAYLIST_LIMIT = 20
MAX_PLAYLIST_LIMIT = 100
STATS_TOP_LIMIT = 10
SIMILARITY_COLLECTIONS = {
    "full": "songs_full",
    "balance": "songs_balanced",
    "minimal": "songs_minimal",
}
SEGMENT_COLLECTIONS = {
    "mert": "songs_segments_mert",
    "ast": "songs_segments_ast",
}


vector_db_clients: dict[str, SongVectorDB] = {}
segment_db_clients: dict[str, SongVectorDB] = {}

SEGMENT_CACHE_VERSION = 2


def _normalize_distance_score(distance: float, max_distance: float) -> float:
    if distance <= 0:
        return 100.0
    if max_distance <= 0:
        return 0.0
    if distance >= max_distance:
        return 0.0
    return 100.0 * (1.0 - distance / max_distance)


def _prepare_segment_items(raw_segments: dict) -> list[dict]:
    segment_ids = raw_segments.get("ids")
    if segment_ids is None:
        segment_ids = []
    segment_embeddings = raw_segments.get("embeddings")
    if segment_embeddings is None:
        segment_embeddings = []
    segment_metadatas = raw_segments.get("metadatas")
    if segment_metadatas is None:
        segment_metadatas = []

    items: list[dict] = []
    for seg_id, embedding, metadata in zip(
        segment_ids,
        segment_embeddings,
        segment_metadatas,
    ):
        if embedding is None or not isinstance(metadata, dict):
            continue
        segment_index = metadata.get("segment_index")
        if isinstance(segment_index, (int, float)):
            segment_index = int(segment_index)
        else:
            segment_index = len(items)
        items.append(
            {
                "segment_id": str(seg_id),
                "embedding": list(embedding),
                "metadata": metadata,
                "segment_index": segment_index,
            }
        )

    items.sort(key=lambda item: item["segment_index"])
    return items


def _filter_segment_items(
    items: list[dict],
    max_seconds: float,
    skip_seconds: float,
    skip_end_seconds: float,
) -> list[dict]:
    if not items:
        return []

    max_end_sec = 0.0
    if skip_end_seconds > 0:
        for item in items:
            end_sec = item["metadata"].get("segment_end_sec")
            if isinstance(end_sec, (int, float)):
                max_end_sec = max(max_end_sec, float(end_sec))

    filtered: list[dict] = []
    for item in items:
        metadata = item["metadata"]
        start_sec = metadata.get("segment_start_sec")
        end_sec = metadata.get("segment_end_sec")

        if not isinstance(start_sec, (int, float)):
            filtered.append(item)
            continue

        start_value = float(start_sec)
        if (
            skip_end_seconds > 0
            and isinstance(end_sec, (int, float))
            and max_end_sec > 0
            and float(end_sec) > max_end_sec - skip_end_seconds
        ):
            continue
        if skip_seconds > 0 and start_value < skip_seconds:
            continue
        if max_seconds > 0 and start_value >= max_seconds:
            continue

        filtered.append(item)

    return filtered


class ResponseMeta(BaseModel):
    request_id: str = Field(default_factory=get_request_id)
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


class SimilarSongItem(BaseModel):
    song: SongSummary
    distance: float


class SegmentSimilarItem(BaseModel):
    song: SongSummary
    score: float
    hit_count: int
    coverage: float
    density: float


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


class PlaylistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    items: list[str] = Field(min_length=1, max_length=100)
    privacy: str = Field(default="PRIVATE", pattern="^(PUBLIC|UNLISTED|PRIVATE)$")
    mode: Optional[str] = Field(default=None, max_length=50)
    header_comment: Optional[str] = Field(default=None, max_length=2000)


class PlaylistCreateResponse(BaseModel):
    playlist_id: str
    playlist_url: str
    created_count: int
    skipped_count: int
    unresolved_items: list[str]


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


def _get_vector_client(key: str) -> SongVectorDB:
    collection = SIMILARITY_COLLECTIONS.get(key)
    if not collection:
        raise HTTPException(status_code=400, detail="Unsupported vector db")

    client = vector_db_clients.get(collection)
    if client is None:
        try:
            client = SongVectorDB(collection_name=collection)
        except Exception as exc:  # pragma: no cover - remote client init
            raise HTTPException(
                status_code=500, detail="Failed to initialize vector store"
            ) from exc
        vector_db_clients[collection] = client
    return client


def _get_segment_client(key: str) -> SongVectorDB:
    collection = SEGMENT_COLLECTIONS.get(key)
    if not collection:
        raise HTTPException(status_code=400, detail="Unsupported segment db")

    client = segment_db_clients.get(collection)
    if client is None:
        try:
            client = SongVectorDB(collection_name=collection)
        except Exception as exc:  # pragma: no cover - remote client init
            raise HTTPException(
                status_code=500, detail="Failed to initialize segment vector store"
            ) from exc
        segment_db_clients[collection] = client
    return client


def _log_warning(event: str, **payload) -> None:
    logger.warning(
        event,
        extra={
            "request_id": get_request_id(),
            "payload": {"event": event, **payload},
        },
    )


def _log_error(event: str, **payload) -> None:
    logger.error(
        event,
        extra={
            "request_id": get_request_id(),
            "payload": {"event": event, **payload},
        },
    )


def _log_debug(event: str, **payload) -> None:
    logger.debug(
        event,
        extra={
            "request_id": get_request_id(),
            "payload": {"event": event, **payload},
        },
    )


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

    resolved_counts = {
        "full": 0,
        "balance": 0,
        "minimal": 0,
        "seg_mert": 0,
        "seg_ast": 0,
    }
    name_aliases = {
        "full": "full",
        "songs_full": "full",
        "songs_segments_full": "full",
        "balance": "balance",
        "balanced": "balance",
        "songs_balance": "balance",
        "songs_balanced": "balance",
        "songs_segments_balance": "balance",
        "minimal": "minimal",
        "songs_minimal": "minimal",
        "songs_segments_minimal": "minimal",
        "seg_mert": "seg_mert",
        "songs_segments_mert": "seg_mert",
        "seg_ast": "seg_ast",
        "songs_segments_ast": "seg_ast",
    }

    for name, count in rows:
        alias = name_aliases.get(str(name).lower())
        if not alias:
            continue
        resolved_counts[alias] = count

    return DbCollectionCounts(**resolved_counts)


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
    offset: int = Query(
        default=0,
        ge=0,
        description="Offset of the first song to return",
    ),
):
    try:
        if keyword and keyword.strip():
            trimmed = keyword.strip()
            total = song_metadata_db.count_by_keyword(trimmed)
            records = song_metadata_db.search_by_keyword(
                trimmed,
                limit=limit,
                offset=offset,
            )
        else:
            total = song_metadata_db.count_songs()
            records = song_metadata_db.list_all(limit=limit, offset=offset)

        songs = [
            _convert_song_summary(song_id, metadata) for song_id, metadata in records
        ]
        return build_envelope(songs, total=total, limit=limit, offset=offset)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500, detail="Database error while loading songs"
        ) from exc


@app.get(
    "/api/songs/{song_id}/similar",
    response_model=ResponseEnvelope[list[SimilarSongItem]],
)
async def get_similar_songs(
    song_id: str,
    request: Request,
    db: str = Query(
        default="full",
        description="Vector DB to query",
        pattern="^(full|balance|minimal)$",
    ),
    n_results: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Number of similar songs to return",
    ),
):
    client = _get_vector_client(db)
    collection_name = getattr(client.collection, "name", None)
    request_context = {
        "song_id": song_id,
        "db": db,
        "collection": collection_name,
        "path": request.url.path,
    }

    base_song = client.get_song(song_id)
    _log_debug(
        "similar_song_lookup_result",
        **{**request_context, "result": "found" if base_song else "missing"},
    )

    if base_song is None:
        _log_warning("similar_song_not_found", reason="song_missing", **request_context)
        raise HTTPException(
            status_code=404, detail="Song not found in the selected collection"
        )

    embedding = base_song.get("embedding")
    if embedding is None:
        _log_warning(
            "similar_song_embedding_missing",
            reason="embedding_missing",
            **request_context,
        )
        raise HTTPException(
            status_code=404, detail="Song embedding missing from vector store"
        )

    embedding_vector = list(embedding)
    if not embedding_vector:
        _log_warning(
            "similar_song_embedding_missing",
            song_id=song_id,
            db=db,
            path=request.url.path,
        )
        raise HTTPException(
            status_code=404, detail="Song embedding missing from vector store"
        )

    try:
        raw_results = client.search_similar(
            embedding_vector,
            n_results=n_results + 1,
            where={"excluded_from_search": {"$ne": True}},
        )
    except Exception as exc:  # pragma: no cover - vector DB runtime errors
        _log_error(
            "similar_song_query_failed",
            song_id=song_id,
            db=db,
            error=str(exc),
            path=request.url.path,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to search similar songs: {exc}",
        ) from exc

    candidate_ids = raw_results.get("ids", [[]])
    candidate_distances = raw_results.get("distances", [[]])
    ids = candidate_ids[0] if candidate_ids else []
    distances = candidate_distances[0] if candidate_distances else []

    if not ids:
        return build_envelope([], total=0, limit=n_results)

    metadata_map = song_metadata_db.get_songs_as_dict(ids)
    similar_items: list[SimilarSongItem] = []
    for candidate_id, distance in zip(ids, distances):
        if candidate_id == song_id:
            continue
        metadata = metadata_map.get(candidate_id)
        if not metadata:
            continue
        similar_items.append(
            SimilarSongItem(
                song=_convert_song_summary(candidate_id, metadata),
                distance=float(distance),
            )
        )
        if len(similar_items) >= n_results:
            break

    return build_envelope(similar_items, total=len(similar_items), limit=n_results)


@app.get(
    "/api/songs/{song_id}/similar-segments",
    response_model=ResponseEnvelope[list[SegmentSimilarItem]],
)
async def get_similar_segments(
    song_id: str,
    request: Request,
    collection: str = Query(
        default="mert",
        description="Segment vector collection",
        pattern="^(mert|ast)$",
    ),
    n_results: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Number of similar songs to return",
    ),
    search_topk: int = Query(
        default=5,
        ge=1,
        le=50,
        description="Candidates per segment",
    ),
    max_seconds: float = Query(
        default=120.0,
        ge=0.0,
        le=600.0,
        description="Maximum seconds of the song to include (0 for no limit)",
    ),
    skip_seconds: float = Query(
        default=10.0,
        ge=0.0,
        le=300.0,
        description="Skip seconds from the start",
    ),
    skip_end_seconds: float = Query(
        default=10.0,
        ge=0.0,
        le=300.0,
        description="Skip seconds from the end",
    ),
    distance_max: float = Query(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Maximum cosine distance to treat as a strong match",
    ),
):
    client = _get_segment_client(collection)
    collection_name = getattr(client.collection, "name", None)
    request_context = {
        "song_id": song_id,
        "collection": collection,
        "db": collection_name,
        "path": request.url.path,
    }

    params_hash = build_params_hash(
        {
            "version": SEGMENT_CACHE_VERSION,
            "collection": collection,
            "n_results": n_results,
            "search_topk": search_topk,
            "max_seconds": max_seconds,
            "skip_seconds": skip_seconds,
            "skip_end_seconds": skip_end_seconds,
            "distance_max": distance_max,
        }
    )

    cached = None
    if collection_name:
        cached = get_segment_search_cache(collection_name, song_id, params_hash)

    if cached is None:
        try:
            raw_segments = client.collection.get(
                where={"source_song_id": song_id},
                include=["embeddings", "metadatas"],
            )
        except Exception as exc:  # pragma: no cover - vector DB runtime errors
            _log_error(
                "segment_song_lookup_failed",
                error=str(exc),
                **request_context,
            )
            raise HTTPException(
                status_code=502,
                detail=f"Failed to load song segments: {exc}",
            ) from exc
        segment_items = _prepare_segment_items(raw_segments)
        if not segment_items:
            _log_warning("segment_song_not_found", **request_context)
            raise HTTPException(
                status_code=404,
                detail="Song segments not found in the selected collection",
            )

        filtered_segments = _filter_segment_items(
            segment_items,
            max_seconds=max_seconds,
            skip_seconds=skip_seconds,
            skip_end_seconds=skip_end_seconds,
        )

        if not filtered_segments:
            raise HTTPException(
                status_code=404,
                detail="Song segments not found in the selected range",
            )

        requested_topk = max(1, search_topk)
        total_query_segments = len(filtered_segments)

        where_filter = {
            "$and": [
                {"excluded_from_search": {"$ne": True}},
                {"source_song_id": {"$ne": song_id}},
            ]
        }

        similar_id_counter: Counter[str] = Counter()
        similar_score_counter: Counter[str] = Counter()
        song_segment_hits: dict[str, set[int]] = {}
        song_density_hits: Counter[str] = Counter()

        for seg_list_index, item in enumerate(filtered_segments):
            seg_id = item["segment_id"]
            embedding = item["embedding"]
            metadata = item["metadata"]

            try:
                search_results = client.search_similar(
                    embedding,
                    n_results=requested_topk,
                    where=where_filter,
                )
            except Exception as exc:  # pragma: no cover - vector DB runtime errors
                _log_error(
                    "segment_search_failed",
                    error=str(exc),
                    **request_context,
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to search segment neighbors: {exc}",
                ) from exc

            ids = (search_results.get("ids") or [[]])[0]
            distances = (search_results.get("distances") or [[]])[0]

            filtered_results: list[tuple[str, float]] = []
            for candidate_id, distance in zip(ids, distances):
                candidate_key = str(candidate_id)
                if candidate_key == seg_id:
                    continue
                try:
                    distance_value = float(distance)
                except (TypeError, ValueError):
                    continue
                filtered_results.append((candidate_key, distance_value))
                if len(filtered_results) >= requested_topk:
                    break

            segment_index = metadata.get("segment_index")
            if not isinstance(segment_index, int):
                segment_index = seg_list_index

            for candidate_key, distance_value in filtered_results:
                base_song_id = candidate_key.split("::", 1)[0]
                song_segment_hits.setdefault(base_song_id, set()).add(segment_index)
                if distance_value < distance_max:
                    song_density_hits.update([base_song_id])
                similar_id_counter.update([candidate_key])
                distance_score = _normalize_distance_score(
                    distance_value,
                    distance_max,
                )
                similar_score_counter[candidate_key] += distance_score

        if not similar_id_counter:
            cached = []
        else:
            song_counter: Counter[str] = Counter()
            song_score_counter: Counter[str] = Counter()

            for segment_id, count in similar_id_counter.items():
                base_song_id = segment_id.split("::", 1)[0]
                if base_song_id == song_id:
                    continue
                song_counter[base_song_id] += count

            for segment_id, score in similar_score_counter.items():
                base_song_id = segment_id.split("::", 1)[0]
                if base_song_id == song_id:
                    continue
                song_score_counter[base_song_id] += score

            final_score_map: dict[str, float] = {}
            normalized_topk = max(1, search_topk)
            for candidate_id in song_counter.keys():
                coverage_hits = len(song_segment_hits.get(candidate_id, set()))
                coverage = (
                    coverage_hits / total_query_segments
                    if total_query_segments > 0
                    else 0.0
                )
                density_hits = song_density_hits.get(candidate_id, 0)
                density_norm = (
                    density_hits / (total_query_segments * normalized_topk)
                    if total_query_segments > 0
                    else 0.0
                )
                score_sum = song_score_counter.get(candidate_id, 0.0)
                final_score_map[candidate_id] = (
                    score_sum * (0.5 + 0.5 * coverage) * (0.5 + 0.5 * density_norm)
                )

            ranked_song_ids = sorted(
                song_counter.keys(),
                key=lambda sid: (
                    final_score_map.get(sid, 0.0),
                    song_score_counter.get(sid, 0.0),
                    song_counter.get(sid, 0),
                ),
                reverse=True,
            )

            results: list[tuple[str, float, int, float, float]] = []
            for candidate_id in ranked_song_ids:
                if len(results) >= n_results:
                    break
                coverage_hits = len(song_segment_hits.get(candidate_id, set()))
                coverage = (
                    coverage_hits / total_query_segments
                    if total_query_segments > 0
                    else 0.0
                )
                density_hits = song_density_hits.get(candidate_id, 0)
                density_norm = (
                    density_hits / (total_query_segments * normalized_topk)
                    if total_query_segments > 0
                    else 0.0
                )
                final_score = final_score_map.get(candidate_id, 0.0)
                results.append(
                    (
                        candidate_id,
                        final_score,
                        song_counter.get(candidate_id, 0),
                        coverage,
                        density_norm,
                    )
                )

            cached = results

        if collection_name and cached:
            save_segment_search_cache(
                collection_name=collection_name,
                song_id=song_id,
                params_hash=params_hash,
                results=cached,
            )

    song_ids = [song_id for song_id, _, _, _, _ in cached]
    metadata_map = song_metadata_db.get_songs_as_dict(song_ids) if song_ids else {}
    items: list[SegmentSimilarItem] = []
    for candidate_id, score, hit_count, coverage, density in cached:
        metadata = metadata_map.get(candidate_id)
        if not metadata:
            continue
        items.append(
            SegmentSimilarItem(
                song=_convert_song_summary(candidate_id, metadata),
                score=float(score),
                hit_count=int(hit_count),
                coverage=float(coverage),
                density=float(density),
            )
        )

    return build_envelope(items, total=len(items), limit=n_results)


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


@app.post(
    "/api/playlists/create",
    response_model=ResponseEnvelope[PlaylistCreateResponse],
)
async def create_playlist(payload: PlaylistCreateRequest, request: Request):
    deduped_song_ids: list[str] = []
    seen_song_ids: set[str] = set()
    for item in payload.items:
        song_id = str(item).strip()
        if not song_id or song_id in seen_song_ids:
            continue
        seen_song_ids.add(song_id)
        deduped_song_ids.append(song_id)

    if not deduped_song_ids:
        raise HTTPException(status_code=400, detail="No valid song items provided")

    songs_meta = song_metadata_db.get_songs_as_dict(deduped_song_ids)
    unresolved_items: list[str] = []
    song_data: list[tuple[str, bool]] = []
    playlist_items: list[dict] = []

    for seq, song_id in enumerate(deduped_song_ids, start=1):
        metadata = songs_meta.get(song_id)
        if not metadata:
            unresolved_items.append(song_id)
            continue

        youtube_id = str(metadata.get("youtube_id") or "").strip()
        if youtube_id:
            song_data.append((youtube_id, True))
        else:
            query = " ".join(
                part.strip()
                for part in [metadata.get("song_title") or "", metadata.get("artist_name") or ""]
                if str(part).strip()
            ).strip()
            if not query:
                unresolved_items.append(song_id)
                continue
            song_data.append((query, False))

        playlist_items.append(
            {
                "seq": seq,
                "song_id": song_id,
                "cosine_distance": 0.0,
            }
        )

    if not song_data:
        raise HTTPException(status_code=400, detail="No resolvable songs were provided")

    try:
        from core.ytmusic_manager import YTMusicManager
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="ytmusicapi is not installed. Run `uv sync` to install dependencies.",
        ) from exc

    browser_file = os.getenv("YTMUSIC_BROWSER_FILE", "browser.json")
    try:
        yt_manager = YTMusicManager(browser_file=browser_file)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "YouTube Music is not configured. "
                f"Set YTMUSIC_BROWSER_FILE or place browser.json in api/. ({exc})"
            ),
        ) from exc

    playlist_name = payload.name.strip()
    playlist_result = yt_manager.create_or_replace_playlist(
        playlist_name=playlist_name,
        song_data=song_data,
        description=payload.description,
        privacy=payload.privacy,
        verbose=False,
    )

    playlist_id = str(playlist_result.get("playlist_id") or "").strip()
    if not playlist_id:
        raise HTTPException(status_code=502, detail="Failed to create playlist on YouTube")

    not_found_items = [str(item).strip() for item in playlist_result.get("not_found", [])]
    unresolved_items.extend(item for item in not_found_items if item)
    unresolved_items = list(dict.fromkeys(unresolved_items))

    created_count = len(playlist_result.get("found_songs", []))
    skipped_count = max(0, len(song_data) - created_count)
    playlist_url = f"https://music.youtube.com/playlist?list={playlist_id}"

    creator_sub = request.headers.get("x-user-sub", "public-user")
    save_ok = playlist_db.save_playlist_result(
        playlist_id=playlist_id,
        playlist_name=playlist_name,
        playlist_url=playlist_url,
        creator_sub=creator_sub,
        items=playlist_items[:created_count],
        header_comment=payload.header_comment,
    )
    if not save_ok:
        _log_warning(
            "playlist_history_save_failed",
            playlist_id=playlist_id,
            creator_sub=creator_sub,
            mode=payload.mode,
            path=request.url.path,
        )

    return build_envelope(
        PlaylistCreateResponse(
            playlist_id=playlist_id,
            playlist_url=playlist_url,
            created_count=created_count,
            skipped_count=skipped_count,
            unresolved_items=unresolved_items,
        ),
        total=1,
        limit=1,
    )


@app.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
