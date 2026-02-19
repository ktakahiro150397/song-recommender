## Song Recommender API (FastAPI + uv)

This directory hosts the mocked FastAPI backend that mirrors the DTOs consumed by the Next.js dashboard. It currently exposes the Phase 1 stats endpoints plus catalog and playlist mocks.

### Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (used for dependency management and scripts)

### Install dependencies

```bash
uv sync
```

### Start the dev server

```bash
uv run uvicorn main:app --reload --port 8000
```

The endpoints will be available at `http://localhost:8000/api/...`.

### Available endpoints

- `GET /api/health`
- `GET /api/stats/overview`
- `GET /api/stats/playlists`
- `GET /api/stats/db-collections`
- `GET /api/songs?keyword=`
- `GET /api/playlists`
- `GET /api/playlists/{playlist_id}`
- `POST /api/playlists/create`

All endpoints respond using the shared `{ "data": ..., "error": ..., "meta": ... }` envelope defined in the platform docs.
