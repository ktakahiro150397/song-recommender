import pytest
from fastapi.testclient import TestClient

import main

pytestmark = pytest.mark.smoke


SONG_RECORDS = [
    (
        "Luminous Path [abc123].wav",
        {
            "song_title": "Luminous Path",
            "artist_name": "Rina Amethyst",
            "source_dir": "data/rina",
            "bpm": 122,
            "youtube_id": "abc123",
            "file_extension": ".wav",
            "file_size_mb": 14.2,
            "registered_at": "2026-02-10T12:00:00Z",
            "excluded_from_search": False,
        },
    ),
    (
        "City Bloom [xyz987].wav",
        {
            "song_title": "City Bloom",
            "artist_name": "Toshiro Park",
            "source_dir": "data/toshiro",
            "bpm": 128,
            "youtube_id": "xyz987",
            "file_extension": ".wav",
            "file_size_mb": 16.7,
            "registered_at": "2026-02-11T12:00:00Z",
            "excluded_from_search": False,
        },
    ),
]

PLAYLIST_HEADERS = [
    {
        "playlist_id": "PL_first",
        "playlist_name": "Night Glide Set",
        "playlist_url": "https://music.youtube.com/playlist?list=PL_first",
        "creator_sub": "user-sub-1",
        "header_comment": "City lights inspired chain",
        "created_at": "2026-02-10T12:00:00Z",
    }
]

PLAYLIST_ITEMS = {
    "PL_first": [
        {
            "seq": 1,
            "song_id": SONG_RECORDS[0][0],
            "cosine_distance": 0.012,
        },
        {
            "seq": 2,
            "song_id": SONG_RECORDS[1][0],
            "cosine_distance": 0.017,
        },
    ]
}

PLAYLIST_COMMENTS = {
    "PL_first": [
        {
            "id": 1,
            "playlist_id": "PL_first",
            "user_sub": "user-sub-2",
            "display_name": "Nao",
            "comment": "Great transitions!",
            "is_deleted": False,
            "created_at": "2026-02-10T12:05:00Z",
        }
    ]
}


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    monkeypatch.setattr(main.song_metadata_db, "count_songs", lambda: len(SONG_RECORDS))
    monkeypatch.setattr(
        main.song_metadata_db,
        "get_total_processed_data_size_gb",
        lambda: 812.4,
    )
    monkeypatch.setattr(
        main.song_metadata_db,
        "list_all",
        lambda limit=main.DEFAULT_SONG_LIMIT: SONG_RECORDS[:limit],
    )
    monkeypatch.setattr(
        main.song_metadata_db,
        "search_by_keyword",
        lambda keyword, limit=main.DEFAULT_SONG_LIMIT: [
            record
            for record in SONG_RECORDS[:limit]
            if keyword.lower() in record[0].lower()
        ],
    )
    monkeypatch.setattr(
        main.song_metadata_db,
        "get_songs_as_dict",
        lambda song_ids: {sid: meta for sid, meta in SONG_RECORDS if sid in song_ids},
    )

    monkeypatch.setattr(main.channel_db_client, "get_channel_count", lambda: 42)
    monkeypatch.setattr(
        main.song_queue_db_client,
        "get_counts",
        lambda: {"pending": 6, "processed": 1540, "failed": 12, "total": 1558},
    )

    monkeypatch.setattr(
        main.playlist_db,
        "get_top_selected_songs",
        lambda limit=main.STATS_TOP_LIMIT: [
            {"song_id": SONG_RECORDS[0][0], "count": 48}
        ][:limit],
    )
    monkeypatch.setattr(
        main.playlist_db,
        "get_top_selected_artists",
        lambda limit=main.STATS_TOP_LIMIT: [
            {"artist_name": SONG_RECORDS[0][1]["artist_name"], "count": 62}
        ][:limit],
    )
    monkeypatch.setattr(
        main.playlist_db,
        "get_top_selected_start_songs",
        lambda limit=main.STATS_TOP_LIMIT: [
            {"song_id": SONG_RECORDS[1][0], "count": 24}
        ][:limit],
    )

    def _filter_headers(keyword=None, limit=main.DEFAULT_PLAYLIST_LIMIT):
        if keyword:
            filtered = [
                header
                for header in PLAYLIST_HEADERS
                if keyword.lower() in header["playlist_name"].lower()
            ]
        else:
            filtered = PLAYLIST_HEADERS
        return filtered[:limit]

    monkeypatch.setattr(main.playlist_db, "list_playlist_headers", _filter_headers)
    monkeypatch.setattr(
        main.playlist_db,
        "get_playlist_items",
        lambda playlist_id: PLAYLIST_ITEMS.get(playlist_id, []),
    )
    monkeypatch.setattr(
        main.playlist_db,
        "list_playlist_comments",
        lambda playlist_id: PLAYLIST_COMMENTS.get(playlist_id, []),
    )

    monkeypatch.setattr(
        main,
        "_load_collection_counts",
        lambda: main.DbCollectionCounts(
            full=2480,
            balance=1724,
            minimal=617,
            seg_mert=14890,
            seg_ast=14932,
        ),
    )

    monkeypatch.setattr(
        main,
        "get_display_names_by_subs",
        lambda subs: {
            sub: f"Display {index}" for index, sub in enumerate(subs, start=1)
        },
    )


@pytest.fixture()
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stats_overview_endpoint(client):
    response = client.get("/api/stats/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["total_songs"] == len(SONG_RECORDS)
    assert payload["meta"]["total"] is None


def test_stats_playlists_endpoint(client):
    response = client.get("/api/stats/playlists")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["top_songs"], "expected at least one top song"


def test_db_collection_counts_endpoint(client):
    response = client.get("/api/stats/db-collections")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total"] == sum(payload["data"].values())


def test_list_songs_endpoint(client):
    response = client.get("/api/songs")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == len(SONG_RECORDS)
    assert payload["meta"]["total"] == len(SONG_RECORDS)


def test_list_playlists_endpoint(client):
    response = client.get("/api/playlists")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == len(PLAYLIST_HEADERS)
    first_entry = payload["data"][0]
    assert first_entry["header"]["creator_display_name"].startswith("Display ")
    assert len(first_entry["items"]) == len(
        PLAYLIST_ITEMS[PLAYLIST_HEADERS[0]["playlist_id"]]
    )
