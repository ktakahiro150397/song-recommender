# Next.js UI Migration Plan and API Design

## Scope (Next.js UI pages)
- TOP (home_page)
- Song Search
- YouTube Registration
- Playlist History
- Registered Content Management
- DB Maintenance
- User Settings

## Auth Policy
- Public: read-only browsing for TOP, Song Search (browse), Playlist History (browse)
- Auth required: YouTube playlist creation, comments, deletions, registrations, maintenance, user settings
- Auth method: Google OAuth on Next.js, API validates JWT

## Auth Spec (JWT + Admin)
- JWT claims: sub, email, name, picture, exp, iat, iss, aud
- Admin allowlist: ADMIN_EMAILS or ADMIN_SUBS (either match grants admin)
- Auth required endpoints return 401 if missing/invalid token
- Admin endpoints return 403 if not in allowlist
- For YouTube playlist creation, the client sends Google access token in X-Google-Access-Token

## Page Mapping
- TOP (home_page)
  - DB stats, playlist stats, feature stats
  - Public
- Song Search
  - Search, similar songs, chain search
  - Public for browse; auth for YouTube playlist creation
- YouTube Registration
  - Register channel/video/playlist URLs
  - Auth required
- Playlist History
  - Browse playlists
  - Auth required for comment create/delete and playlist delete
- Registered Content Management
  - Channel list edit/delete; song queue list/reset failed
  - Auth required
- DB Maintenance
  - Song list, delete, excluded flag update
  - Auth required
- User Settings
  - Update display name
  - Auth required

---

# API Design (Draft)

## Conventions
- Base URL: /api
- Auth header: Authorization: Bearer <jwt>
- JSON responses use { "data": ..., "error": ... }
- Pagination: ?limit= and ?offset= where needed

## Response and DTO Design (Draft)

### Response Envelope
```json
{
  "data": {},
  "error": null,
  "meta": {
    "request_id": "...",
    "total": 0,
    "limit": 50,
    "offset": 0
  }
}
```

### Error Shape
```json
{
  "error": {
    "code": "unauthorized",
    "message": "Login required",
    "details": {}
  }
}
```

### Common DTOs

#### UserProfile
```json
{
  "sub": "google-sub",
  "email": "user@example.com",
  "name": "Display Name",
  "alias": "Optional Alias",
  "picture": "https://...",
  "is_admin": false
}
```

#### SongSummary
```json
{
  "song_id": "Song Name [videoId].wav",
  "song_title": "Song Name",
  "artist_name": "Artist",
  "source_dir": "data/artist",
  "bpm": 120.0,
  "youtube_id": "videoId",
  "file_extension": ".wav",
  "file_size_mb": 12.34,
  "registered_at": "2026-02-10T12:00:00Z",
  "excluded_from_search": false
}
```

#### SimilarSongItem
```json
{
  "song": { "...": "SongSummary" },
  "distance": 0.012345
}
```

#### SegmentSimilarItem
```json
{
  "song": { "...": "SongSummary" },
  "score": 82.5,
  "hit_count": 12,
  "coverage": 0.64,
  "density": 0.18
}
```

#### ChainSearchItem
```json
{
  "seq": 1,
  "song": { "...": "SongSummary" },
  "distance_or_score": 0.0
}
```

#### PlaylistHeader
```json
{
  "playlist_id": "PL...",
  "playlist_name": "My Playlist",
  "playlist_url": "https://music.youtube.com/playlist?list=...",
  "creator_sub": "google-sub",
  "creator_display_name": "Name",
  "created_at": "2026-02-10T12:00:00Z",
  "header_comment": "Optional comment"
}
```

#### PlaylistItem
```json
{
  "seq": 1,
  "song_id": "Song Name [videoId].wav",
  "cosine_distance": 0.012345,
  "source_dir": "data/artist"
}
```

#### PlaylistComment
```json
{
  "id": 123,
  "playlist_id": "PL...",
  "user_sub": "google-sub",
  "display_name": "Name",
  "comment": "Nice playlist",
  "is_deleted": false,
  "created_at": "2026-02-10T12:00:00Z"
}
```

#### ChannelItem
```json
{
  "id": 1,
  "channel_id": "UC...",
  "channel_name": "Channel",
  "url": "https://youtube.com/channel/...",
  "thumbnail_url": "https://...",
  "registered_at": "2026-02-10T12:00:00Z"
}
```

#### SongQueueItem
```json
{
  "id": 1,
  "video_id": "videoId",
  "url": "https://youtu.be/...",
  "title": "Title",
  "artist_name": "Artist",
  "status": "pending",
  "registered_at": "2026-02-10T12:00:00Z"
}
```

#### Stats DTOs (overview)
```json
{
  "total_songs": 0,
  "total_channels": 0,
  "queue_counts": { "pending": 0, "processed": 0, "failed": 0, "total": 0 },
  "total_size_gb": 0.0
}
```

## Public Endpoints

### Health
- GET /api/health
  - Returns service status

### Home Dashboard
- GET /api/stats/overview
  - total_songs, total_channels, queue_counts, total_size_gb
- GET /api/stats/playlists
  - top_songs, top_artists, top_start_songs
- GET /api/stats/playlists/me
  - same as above for current user (auth optional; returns empty if no user)
- GET /api/stats/db-collections
  - counts for Full/Balance/Minimal, Seg MERT/AST
- GET /api/stats/feature-sample
  - sample_size, feature_groups, stats

### Song Search
- GET /api/songs
  - Query: keyword, limit, recent, random
  - Returns list of song metadata
- GET /api/songs/{song_id}
  - Returns song metadata
- GET /api/songs/{song_id}/similar
  - Query: db=full|balance|minimal, n_results
- GET /api/songs/{song_id}/similar-segments
  - Query: collection=mert|ast, n_results, search_topk, max_seconds, skip_seconds, skip_end_seconds, distance_max
- POST /api/songs/chain-search
  - Body: start_song_id, n_songs, mode=mbf|mert|ast, source_dir_filters, bpm_filter

### Playlist History (browse)
- GET /api/playlists
  - Query: keyword, creator=me|all, limit
- GET /api/playlists/{playlist_id}
  - Returns header and items
- GET /api/playlists/{playlist_id}/comments
  - Query: limit, offset

## Auth Required Endpoints

### Auth/User
- GET /api/me
  - Returns user profile
- PATCH /api/me/alias
  - Body: alias

### YouTube Registration
- POST /api/youtube/register
  - Body: { urls: [ ... ] }
  - Returns batch results

### Playlist Creation
- POST /api/playlists/create
  - Body: { name, description, items: [song_id], mode, privacy }
  - Creates YouTube playlist and persists history
  - Requires X-Google-Access-Token header

### Playlist History (write)
- POST /api/playlists/{playlist_id}/comments
  - Body: comment
- DELETE /api/playlists/{playlist_id}/comments/{comment_id}
- DELETE /api/playlists/{playlist_id}
  - Only creator can delete

### Registered Content Management
- GET /api/channels
  - Query: keyword, sort, limit, offset
- PATCH /api/channels/{channel_id}
  - Body: channel_name
- DELETE /api/channels/{channel_id}

- GET /api/song-queue
  - Query: status, keyword, limit, offset
- POST /api/song-queue/reset-failed

### DB Maintenance
- GET /api/admin/songs
  - Query: keyword, source_dir, include_excluded, limit, offset
- DELETE /api/admin/songs
  - Body: { song_ids: [...] }
- PATCH /api/admin/songs/excluded
  - Body: { song_ids: [...], excluded: true|false }

---

## Notes
- Admin endpoints can be guarded by a simple allowlist of email or sub in config.
- Heavy operations should use background tasks and return job status if needed.
- Playlist creation requires YouTube auth on server side.

---

# API Priorities and MVP Scope

## MVP Phase 1 (Public Read-only)
- Health
  - GET /api/health
- Home dashboard stats
  - GET /api/stats/overview
  - GET /api/stats/playlists
  - GET /api/stats/db-collections
- Song search (browse)
  - GET /api/songs
  - GET /api/songs/{song_id}
  - GET /api/songs/{song_id}/similar
  - GET /api/songs/{song_id}/similar-segments
- Playlist history (browse)
  - GET /api/playlists
  - GET /api/playlists/{playlist_id}
  - GET /api/playlists/{playlist_id}/comments

## MVP Phase 2 (Auth + User Features)
- Auth/User
  - GET /api/me
  - PATCH /api/me/alias
- Playlist comments
  - POST /api/playlists/{playlist_id}/comments
  - DELETE /api/playlists/{playlist_id}/comments/{comment_id}
- Playlist deletion (creator only)
  - DELETE /api/playlists/{playlist_id}
- YouTube playlist creation
  - POST /api/playlists/create

## Phase 3 (Registration + Maintenance)
- YouTube registration
  - POST /api/youtube/register
- Registered content management
  - GET /api/channels
  - PATCH /api/channels/{channel_id}
  - DELETE /api/channels/{channel_id}
  - GET /api/song-queue
  - POST /api/song-queue/reset-failed
- DB maintenance (admin)
  - GET /api/admin/songs
  - DELETE /api/admin/songs
  - PATCH /api/admin/songs/excluded

## Non-MVP (Optional later)
- Feature statistics sampling
  - GET /api/stats/feature-sample
- User-specific playlist stats
  - GET /api/stats/playlists/me

---

# Authorization Rules (Public vs User vs Admin)

## Roles
- Public: no login required
- User: logged-in with valid app JWT
- Admin: logged-in and in allowlist (ADMIN_EMAILS or ADMIN_SUBS)

## Public (Anonymous Allowed)
- Home dashboard stats
  - GET /api/stats/overview
  - GET /api/stats/playlists
  - GET /api/stats/db-collections
- Song search (browse)
  - GET /api/songs
  - GET /api/songs/{song_id}
  - GET /api/songs/{song_id}/similar
  - GET /api/songs/{song_id}/similar-segments
  - POST /api/songs/chain-search (read-only; no playlist creation)
- Playlist history (browse)
  - GET /api/playlists
  - GET /api/playlists/{playlist_id}
  - GET /api/playlists/{playlist_id}/comments

## User (Login Required)
- Profile
  - GET /api/me
  - PATCH /api/me/alias
- Playlist creation (YouTube)
  - POST /api/playlists/create
- Playlist history (write)
  - POST /api/playlists/{playlist_id}/comments
  - DELETE /api/playlists/{playlist_id}/comments/{comment_id}
  - DELETE /api/playlists/{playlist_id} (creator only)
- YouTube registration
  - POST /api/youtube/register
- Registered content management
  - GET /api/channels
  - PATCH /api/channels/{channel_id}
  - DELETE /api/channels/{channel_id}
  - GET /api/song-queue
  - POST /api/song-queue/reset-failed

## Admin (Login + Allowlist)
- DB maintenance
  - GET /api/admin/songs
  - DELETE /api/admin/songs
  - PATCH /api/admin/songs/excluded

## Edge Rules
- If a public endpoint is abused, promote it to User.
- Playlist deletion requires creator_sub match.
- Comment deletion allows author only.

---

# Rate Limiting and Job Design (Async)

## Assumptions
- Song search and chain search can take 60s+.
- Long-running work must be async to avoid request timeouts.

## Rate Limiting (Recommended)
- Public endpoints: basic IP-based limit (e.g. 30 req/min).
- User endpoints: per-user limit (e.g. 60 req/min).
- Playlist creation: per-user limit (e.g. 2 req/min).
- YouTube registration: per-user limit (e.g. 5 req/min).

## Async Job Model
- Long-running endpoints return 202 Accepted with job_id.
- Client polls job status until completed.

## Client Pattern (Polling)
- Start job and store job_id in UI state.
- Poll GET /api/jobs/{job_id} every 2-5 seconds.
- On completed: show result and stop polling.
- On failed: show error and stop polling.

## Job Lifecycle
- POST /api/jobs/search (start)
- GET /api/jobs/{job_id} (status)
- DELETE /api/jobs/{job_id} (cancel, optional)

## Job Status Shape
```json
{
  "job_id": "...",
  "status": "queued|running|completed|failed|canceled",
  "progress": 0.0,
  "started_at": "2026-02-10T12:00:00Z",
  "finished_at": null,
  "result": null,
  "error": null
}
```

## Search Job Types
- similarity_search
- segment_search
- chain_search

## Async Endpoints (Draft)
- POST /api/jobs/search
  - Body: { type, params }
  - Returns: job_id
- GET /api/jobs/{job_id}
  - Returns: JobStatus

## Backend Options
- Simple in-process queue (for single server)
- Redis + RQ/Celery (recommended for reliability)

## Notes
- Use max execution time per job to prevent runaway tasks.
- Persist job results for a short TTL (e.g. 10 minutes).

## Job API Minimal Design

### Request
```json
{
  "type": "similarity_search",
  "params": {
    "song_id": "song.wav",
    "db": "full",
    "n_results": 30
  }
}
```

### Params by Type
- similarity_search
  - song_id, db=full|balance|minimal, n_results
- segment_search
  - song_id, collection=mert|ast, n_results, search_topk, max_seconds, skip_seconds, skip_end_seconds, distance_max
- chain_search
  - start_song_id, n_songs, mode=mbf|mert|ast, source_dir_filters, bpm_filter

### Job Result
```json
{
  "type": "similarity_search",
  "result": {
    "items": [
      { "song": { "...": "SongSummary" }, "distance": 0.012345 }
    ]
  }
}
```

---

# Error Response and Retry Policy

## Error Envelope (Standard)
```json
{
  "data": null,
  "error": {
    "code": "validation_error",
    "message": "Invalid request",
    "details": {}
  }
}
```

## Error Codes
- validation_error (400)
- unauthorized (401)
- forbidden (403)
- not_found (404)
- conflict (409)
- rate_limited (429)
- upstream_error (502)
- server_error (500)

## Retry Policy (Client)
- 429: retry with exponential backoff (1s, 2s, 4s), max 3
- 502/503/504: retry with backoff, max 2
- 500: retry once, then surface error
- 400/401/403/404: do not retry

## UX Handling (Client)
- Show friendly error toast and keep last successful data when possible.
- For job polling, stop polling on failed and show error.
- For 401, prompt re-login and retry once after token refresh.

---

# Audit Logging (Server-side)

## Approach
- Start with file-based JSON Lines logs on the API server.
- Keep schema stable so switching to DB is straightforward.

## Log Fields (JSONL)
```json
{
  "timestamp": "2026-02-10T12:00:00Z",
  "request_id": "...",
  "user_sub": "google-sub",
  "email": "user@example.com",
  "action": "playlist.create",
  "target_id": "PL...",
  "status": "success",
  "ip": "203.0.113.10",
  "user_agent": "...",
  "details": {
    "created_count": 30,
    "skipped_count": 2
  }
}
```

## Storage
- File path: /var/log/song-recommender/audit.log (JSONL)
- Rotation: daily or size-based (e.g. 50MB)

## DB Migration Plan
- Use the same fields as columns in an audit_events table.
- Provide a small adapter that writes both file + DB during migration.

---

# YouTube Playlist Creation (Server-side)

## Recommended Approach
- Use YouTube Data API v3 with per-user OAuth access tokens.
- Next.js obtains Google access token with youtube scope.
- API uses the access token to create playlists on behalf of the user.
- Only allow authenticated users to invoke playlist creation.

## Flow
1. Client posts playlist creation request with song IDs and metadata.
2. API resolves missing YouTube video IDs by search.
3. API calls YouTube Data API v3 to create a playlist for the user.
4. API adds videos to the playlist.
5. API persists playlist header and items into DB.

## Endpoint Contract
- POST /api/playlists/create
  - Request:
    - name: string
    - description: string
    - items: [song_id]
    - privacy: PUBLIC|UNLISTED|PRIVATE
    - mode: mbf|mert|ast (optional; for logging)
    - header_comment: string (optional)
  - Headers:
    - Authorization: Bearer <app-jwt>
    - X-Google-Access-Token: <google-access-token>
  - Response:
    - playlist_id
    - playlist_url
    - created_count
    - skipped_count

## Server Requirements
- Google API client setup for YouTube Data API v3.
- Validate access token (optional tokeninfo check) and handle expiry.
- Rate limiting to prevent abuse (e.g. per-user per-minute).

## Security
- Require auth for the endpoint.
- Optionally restrict to allowlisted users if public service risk is high.
- Log creator_sub and playlist_id for auditing.

---

# YouTube Data API v3 Implementation Design

## Required OAuth Scope
- https://www.googleapis.com/auth/youtube

## Endpoints Used
- POST https://www.googleapis.com/youtube/v3/playlists?part=snippet,status
- POST https://www.googleapis.com/youtube/v3/playlistItems?part=snippet
- GET  https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=1&q=...

## Request Flow (Server)
1. Validate app JWT and read X-Google-Access-Token.
2. Optionally validate token via tokeninfo endpoint.
3. Resolve video IDs for items lacking youtube_id (search query fallback).
4. Create playlist (title, description, privacy).
5. Insert videos to playlist in batches (YouTube API limits per request).
6. Persist playlist header and items to DB.

## Token Validation
- Optional pre-check: GET https://oauth2.googleapis.com/tokeninfo?access_token=...
- Reject if expired or missing scope.

## Error Handling
- 401: missing/invalid app JWT
- 400: missing access token or invalid payload
- 403: access token missing youtube scope
- 429: rate limited by Google API (backoff and retry)
- 5xx: return retryable error to client

## Rate Limiting and Retries
- Per-user rate limit for playlist creation (e.g. 2/min).
- Retry on 429 and 5xx with exponential backoff (e.g. 1s, 2s, 4s).

## Data Mapping
- Playlist name -> playlists.snippet.title
- Playlist description -> playlists.snippet.description
- Privacy -> playlists.status.privacyStatus
- Video IDs -> playlistItems.snippet.resourceId.videoId

## API Response (Server)
- playlist_id
- playlist_url
- created_count
- skipped_count
- unresolved_items (optional list of song_id)

## Implementation Notes
- Use google-api-python-client or direct HTTP requests.
- Prefer direct HTTP to reduce dependency weight if needed.
- Always log request_id, creator_sub, playlist_id, and counts.

---

# YouTube API Implementation (FastAPI Sketch)

## FastAPI Route (Pseudo)
```python
@router.post("/api/playlists/create")
def create_playlist(payload: PlaylistCreateRequest,
           user: User = Depends(require_auth),
           google_token: str = Depends(get_google_access_token)):
  # 1) Validate token (optional tokeninfo)
  if not has_youtube_scope(google_token):
    raise HTTPException(status_code=403, detail="missing youtube scope")

  # 2) Resolve video IDs
  items = resolve_video_ids(payload.items)

  # 3) Create playlist
  playlist_id = youtube_create_playlist(google_token, payload)

  # 4) Add videos (batch)
  created_count, skipped_count, unresolved = youtube_add_videos(
    google_token, playlist_id, items
  )

  # 5) Persist to DB
  save_playlist_history(user.sub, playlist_id, payload, items)

  return {
    "data": {
      "playlist_id": playlist_id,
      "playlist_url": f"https://music.youtube.com/playlist?list={playlist_id}",
      "created_count": created_count,
      "skipped_count": skipped_count,
      "unresolved_items": unresolved,
    },
    "error": None,
  }
```

## Token Extraction (FastAPI)
```python
def get_google_access_token(request: Request) -> str:
  token = request.headers.get("X-Google-Access-Token")
  if not token:
    raise HTTPException(status_code=400, detail="missing google access token")
  return token
```

## YouTube API Calls (HTTP)
```python
def youtube_create_playlist(token: str, payload: PlaylistCreateRequest) -> str:
  url = "https://www.googleapis.com/youtube/v3/playlists?part=snippet,status"
  body = {
    "snippet": {
      "title": payload.name,
      "description": payload.description,
    },
    "status": {
      "privacyStatus": payload.privacy,
    },
  }
  resp = http_post(url, token, body)
  return resp["id"]

def youtube_add_video(token: str, playlist_id: str, video_id: str) -> None:
  url = "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet"
  body = {
    "snippet": {
      "playlistId": playlist_id,
      "resourceId": {
        "kind": "youtube#video",
        "videoId": video_id,
      },
    }
  }
  http_post(url, token, body)
```

## Search Fallback (HTTP)
```python
def youtube_search_video_id(token: str, query: str) -> str | None:
  url = "https://www.googleapis.com/youtube/v3/search"
  params = {
    "part": "snippet",
    "type": "video",
    "maxResults": 1,
    "q": query,
  }
  resp = http_get(url, token, params)
  items = resp.get("items", [])
  if not items:
    return None
  return items[0]["id"]["videoId"]
```

## Client Request Example
```http
POST /api/playlists/create
Authorization: Bearer <app-jwt>
X-Google-Access-Token: <google-access-token>
Content-Type: application/json

{
  "name": "Song Chain Playlist",
  "description": "Auto-generated",
  "items": ["song1.wav", "song2.wav"],
  "privacy": "PUBLIC",
  "mode": "mbf",
  "header_comment": "Optional"
}
```
