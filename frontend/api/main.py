from __future__ import annotations

from typing import Generic, Optional, TypeVar
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

app = FastAPI(
    title="Song Recommender API",
    version="0.1.0",
    description="Mocked endpoints backing the Next.js dashboard",
)


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
    bpm: float
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


mock_stats_overview = StatsOverview(
    total_songs=4821,
    total_channels=318,
    queue_counts=QueueCounts(pending=6, processed=1540, failed=12, total=1558),
    total_size_gb=812.4,
)

mock_stats_playlists = StatsPlaylists(
    top_songs=[
        SongCount(song_id="Luminous Path [abc123].wav", count=48),
        SongCount(song_id="City Bloom [xyz987].wav", count=44),
        SongCount(song_id="Parallel Sun [klm555].wav", count=39),
    ],
    top_artists=[
        ArtistCount(artist_name="Rina Amethyst", count=62),
        ArtistCount(artist_name="Toshiro Park", count=51),
        ArtistCount(artist_name="Hikari Bloom", count=47),
    ],
    top_start_songs=[
        SongCount(song_id="Luminous Path [abc123].wav", count=24),
        SongCount(song_id="Silent Tunnels [uvw222].wav", count=19),
        SongCount(song_id="Signal Drift [pqr444].wav", count=15),
    ],
)

mock_db_counts = DbCollectionCounts(
    full=2480,
    balance=1724,
    minimal=617,
    seg_mert=14890,
    seg_ast=14932,
)

mock_songs = [
    SongSummary(
        song_id="Luminous Path [abc123].wav",
        song_title="Luminous Path",
        artist_name="Rina Amethyst",
        source_dir="data/rina",
        bpm=122,
        youtube_id="abc123",
        file_extension=".wav",
        file_size_mb=14.2,
        registered_at="2026-02-10T12:00:00Z",
        excluded_from_search=False,
    ),
    SongSummary(
        song_id="City Bloom [xyz987].wav",
        song_title="City Bloom",
        artist_name="Toshiro Park",
        source_dir="data/toshiro",
        bpm=128,
        youtube_id="xyz987",
        file_extension=".wav",
        file_size_mb=16.7,
        registered_at="2026-02-10T12:00:00Z",
        excluded_from_search=False,
    ),
    SongSummary(
        song_id="Parallel Sun [klm555].wav",
        song_title="Parallel Sun",
        artist_name="Hikari Bloom",
        source_dir="data/hikari",
        bpm=118,
        youtube_id="klm555",
        file_extension=".wav",
        file_size_mb=13.1,
        registered_at="2026-02-10T12:00:00Z",
        excluded_from_search=False,
    ),
    SongSummary(
        song_id="Silent Tunnels [uvw222].wav",
        song_title="Silent Tunnels",
        artist_name="Echo Fields",
        source_dir="data/echo",
        bpm=110,
        youtube_id="uvw222",
        file_extension=".wav",
        file_size_mb=11.8,
        registered_at="2026-02-10T12:00:00Z",
        excluded_from_search=False,
    ),
]

mock_playlist_history = [
    PlaylistHistoryEntry(
        header=PlaylistHeader(
            playlist_id="PL_first",
            playlist_name="Night Glide Set",
            playlist_url="https://music.youtube.com/playlist?list=PL_first",
            creator_sub="user-sub-1",
            creator_display_name="Rina",
            created_at="2026-02-10T12:00:00Z",
            header_comment="City lights inspired chain",
        ),
        items=[
            PlaylistItem(
                seq=1,
                song_id="Luminous Path [abc123].wav",
                cosine_distance=0.012,
                source_dir="data/rina",
            ),
            PlaylistItem(
                seq=2,
                song_id="City Bloom [xyz987].wav",
                cosine_distance=0.017,
                source_dir="data/toshiro",
            ),
        ],
        comments=[
            PlaylistComment(
                id=1,
                playlist_id="PL_first",
                user_sub="user-sub-2",
                display_name="Nao",
                comment="Great transitions!",
                is_deleted=False,
                created_at="2026-02-10T12:00:00Z",
            )
        ],
    ),
    PlaylistHistoryEntry(
        header=PlaylistHeader(
            playlist_id="PL_second",
            playlist_name="Sunrise Cascade",
            playlist_url="https://music.youtube.com/playlist?list=PL_second",
            creator_sub="user-sub-3",
            creator_display_name="Tak",
            created_at="2026-02-10T12:00:00Z",
            header_comment="Testing chain search results",
        ),
        items=[
            PlaylistItem(
                seq=1,
                song_id="Parallel Sun [klm555].wav",
                cosine_distance=0.011,
                source_dir="data/hikari",
            ),
            PlaylistItem(
                seq=2,
                song_id="Silent Tunnels [uvw222].wav",
                cosine_distance=0.016,
                source_dir="data/echo",
            ),
        ],
        comments=[],
    ),
]


def build_envelope(data, total: Optional[int] = None):
    return ResponseEnvelope(
        data=data,
        error=None,
        meta=ResponseMeta(
            total=total,
            limit=total,
            offset=0,
        ),
    )


@app.get("/api/stats/overview", response_model=ResponseEnvelope[StatsOverview])
async def get_stats_overview():
    return build_envelope(mock_stats_overview)


@app.get("/api/stats/playlists", response_model=ResponseEnvelope[StatsPlaylists])
async def get_stats_playlists():
    return build_envelope(mock_stats_playlists)


@app.get(
    "/api/stats/db-collections", response_model=ResponseEnvelope[DbCollectionCounts]
)
async def get_db_collection_counts():
    total_collections = sum(mock_db_counts.model_dump().values())
    return build_envelope(mock_db_counts, total=total_collections)


@app.get(
    "/api/songs",
    response_model=ResponseEnvelope[list[SongSummary]],
)
async def list_songs(
    keyword: Optional[str] = Query(
        default=None,
        description="Filter by song title, artist name, or song_id",
    )
):
    if keyword:
        lowered = keyword.strip().lower()
        filtered = [
            song
            for song in mock_songs
            if lowered in song.song_title.lower()
            or lowered in song.artist_name.lower()
            or lowered in song.song_id.lower()
        ]
    else:
        filtered = mock_songs

    return build_envelope(filtered, total=len(filtered))


@app.get(
    "/api/playlists",
    response_model=ResponseEnvelope[list[PlaylistHistoryEntry]],
)
async def list_playlists():
    return build_envelope(mock_playlist_history, total=len(mock_playlist_history))


@app.get(
    "/api/playlists/{playlist_id}",
    response_model=ResponseEnvelope[PlaylistHistoryEntry],
)
async def get_playlist_detail(playlist_id: str):
    for playlist in mock_playlist_history:
        if playlist.header.playlist_id == playlist_id:
            return build_envelope(playlist)
    raise HTTPException(status_code=404, detail="Playlist not found")


@app.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
