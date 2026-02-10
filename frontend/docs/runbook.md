# Song Recommender Runbook

_Last updated: 2026-02-10_

## 1. Overview
This runbook describes how to start the FastAPI backend and Next.js frontend, how to deploy them, and how to inspect their observability signals (logs + metrics). Follow the sections in order when bringing up a new environment or debugging incidents.

## 2. Prerequisites
- Python 3.11 with [uv](https://github.com/astral-sh/uv) installed (`pip install uv`)
- Node.js 20.x with npm 10+
- Access to the production MySQL + Chroma stacks and their credentials
- Google OAuth client credentials for NextAuth (see `docs/env-setup.md`)

## 3. Backend (FastAPI) Startup
1. Copy the template environment file and fill in DB credentials:
   ```bash
   cd api
   cp .env.example .env  # if present
   # set MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, etc.
   ```
2. Install Python dependencies with uv:
   ```bash
   cd api
   uv sync
   ```
3. Start the API server locally:
   ```bash
   cd api
   uv run uvicorn main:app --reload --host 0.0.0.0 --port 8001
   ```
4. Health check: `curl http://localhost:8001/api/health` should return `{ "status": "ok" }`.

## 4. Frontend (Next.js) Startup
1. Install dependencies: `npm install`
2. Configure `.env.local` (see `docs/env-setup.md`). Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8001` for local dev.
3. Start dev server: `npm run dev`
4. Visit http://localhost:3000 to verify the UI hits the new API.

## 5. Deployment Notes
- Build artifacts:
  - Backend: containerize with a `uvicorn` entrypoint (`uv run uvicorn main:app --host 0.0.0.0 --port 8001`). Ensure `.env` is supplied at runtime.
  - Frontend: `npm run build && npm run start` or deploy via Vercel after setting the API base URL.
- Minimum environment variables:
  - Backend: `MYSQL_*`, `ADMIN_EMAILS`, `ADMIN_SUBS`, optional `API_LOG_DIR`, `API_LOG_FILENAME`
  - Frontend: `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `NEXT_PUBLIC_API_BASE_URL`
- Restart procedure: stop the old process/container, redeploy, and verify `/api/health` before flipping traffic.

## 6. Observability
- **Structured logs**
  - Path: `api/logs/api.log` (override with `API_LOG_DIR`/`API_LOG_FILENAME`).
  - Format: JSON Lines with fields such as `timestamp`, `level`, `request_id`, `method`, `path`, `status`, `duration_ms`, `client_ip`.
  - Every HTTP response adds an `X-Request-ID` header; use it to correlate client errors with log entries.
- **Metrics endpoint**
  - `GET /api/metrics` returns lightweight in-memory stats: total requests/failures, average latency, per-path counts.
  - Protect the endpoint at the proxy/load-balancer layer if exposed outside trusted networks.
- **Health checks**
  - `GET /api/health` (backend) and `GET /` (frontend) can be used by load balancers.

## 7. Troubleshooting Checklist
1. **API returns 500**
   - Check `api/logs/api.log` for entries with the matching `request_id`.
   - Confirm DB credentials in `api/.env` and connectivity to MySQL/Chroma.
2. **uv sync fails**
   - Ensure build tools (e.g., `build-essential`, `python3-dev`) are installed on the host.
   - Delete `.venv` inside `api/` and retry `uv sync`.
3. **Next.js cannot authenticate**
   - Revisit `docs/env-setup.md`; confirm Google OAuth redirect URIs and secrets.
4. **Metrics look stale**
   - The in-memory collector resets on process restart; ensure requests are actually reaching the server and `uvicorn` is running.

## 8. Operational Tips
- Always tail the JSON log while developing: `tail -f api/logs/api.log | jq`.
- When debugging latency, compare `/api/metrics` averages against client-side timings to isolate frontend vs backend slowness.
- Document schema migrations or DB seeding steps in `docs/dev-progress.md` once finalized.
