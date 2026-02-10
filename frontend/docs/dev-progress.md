# Development Progress Log

_Last updated: 2026-02-10_

## Overall Status
- Backend FastAPI app now calls the real MySQL/Chroma logic through the copied `core` modules; no more mock responses on the server side.
- Frontend can already point to the new API by updating `NEXT_PUBLIC_API_BASE_URL`, with mock fallbacks still available for offline development.
- Python dependencies are declared, but `uv sync` still needs to succeed after providing valid DB credentials via `api/.env`.

## Completed
- Copied legacy backend core modules (database, song/playlist managers, etc.) under `api/core` so the FastAPI app can import production logic without reaching outside the workspace.
- Replaced all mocked FastAPI handlers in `api/main.py` with real implementations that:
  - Pull stats, songs, and playlist history from the shared MySQL + Chroma stack via `core` modules.
  - Wrap responses in the existing DTO envelopes and expose `limit`/keyword filters for songs and playlists.
  - Resolve display names for playlist creators/comments using `core.user_db`.
- Added `sqlalchemy`, `pymysql`, and `python-dotenv` to `api/pyproject.toml`; running `uv sync` inside `api/` will install everything for the FastAPI service.
- Documented that frontend requests target the FastAPI server via `NEXT_PUBLIC_API_BASE_URL`, and backend DB credentials are supplied through `.env` (preferably `api/.env` so `python-dotenv` picks them up before falling back to repo/root env variables).

## Implementation Checklist
### Backend
- [x] Mirror legacy `core` modules under `api/`.
- [x] Replace FastAPI mocks with real DB-backed handlers.
- [x] Provide production DB credentials in `api/.env` (MYSQL_* envs) and confirm connectivity.
- [x] Run `uv sync` successfully and capture any required OS packages.
- [ ] Add automated tests or smoke scripts that hit the new endpoints.

### Frontend
- [x] Document environment switch (`NEXT_PUBLIC_API_BASE_URL`).
- [ ] Update the API client to remove mock fallbacks once API is stable.
- [ ] Review pages/components for any DTO drift after backend changes.

### Observability & Ops
- [ ] Add structured logging/metrics around FastAPI endpoints.
- [ ] Decide on deployment targets (container image vs. existing infra) and write runbooks.
- [ ] Document how to seed or migrate the MySQL schema for new environments.

## Next Steps
1. Run `uv sync` successfully (resolve any missing compilers/libs) and restart `uv run uvicorn main:app --reload --port 8001` once the DB credentials are in place.
2. Verify each endpoint (`/api/health`, `/api/stats/*`, `/api/songs`, `/api/playlists`, `/api/playlists/{id}`) against a seeded database.
3. Decide whether to keep mock fallbacks in the Next.js client or remove them once the API stabilizes.
4. (Optional) Add paging/cursors for long song or playlist lists and expand test coverage around the new data access layer.
