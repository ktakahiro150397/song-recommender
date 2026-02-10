# API Data Models

This document defines request/response DTOs for the API. Use JSON and ISO-8601 timestamps (UTC).

## Conventions
- IDs are strings unless otherwise specified.
- Timestamps are ISO-8601 strings, e.g. "2026-02-10T12:00:00Z".
- Optional fields may be omitted or set to null.

## Response Envelope
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

## Error Shape
```json
{
  "error": {
    "code": "unauthorized",
    "message": "Login required",
    "details": {}
  }
}
```

## Core DTOs

### UserProfile
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

### SongSummary
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

### SimilarSongItem
```json
{
  "song": { "...": "SongSummary" },
  "distance": 0.012345
}
```

### SegmentSimilarItem
```json
{
  "song": { "...": "SongSummary" },
  "score": 82.5,
  "hit_count": 12,
  "coverage": 0.64,
  "density": 0.18
}
```

### ChainSearchItem
```json
{
  "seq": 1,
  "song": { "...": "SongSummary" },
  "distance_or_score": 0.0
}
```

### PlaylistHeader
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

### PlaylistItem
```json
{
  "seq": 1,
  "song_id": "Song Name [videoId].wav",
  "cosine_distance": 0.012345,
  "source_dir": "data/artist"
}
```

### PlaylistComment
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

### ChannelItem
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

### SongQueueItem
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

### StatsOverview
```json
{
  "total_songs": 0,
  "total_channels": 0,
  "queue_counts": { "pending": 0, "processed": 0, "failed": 0, "total": 0 },
  "total_size_gb": 0.0
}
```

### StatsPlaylists
```json
{
  "top_songs": [
    { "song_id": "...", "count": 10 }
  ],
  "top_artists": [
    { "artist_name": "...", "count": 10 }
  ],
  "top_start_songs": [
    { "song_id": "...", "count": 10 }
  ]
}
```

### DbCollectionCounts
```json
{
  "full": 0,
  "balance": 0,
  "minimal": 0,
  "seg_mert": 0,
  "seg_ast": 0
}
```

## Request DTOs

### PlaylistCreateRequest
```json
{
  "name": "Song Chain Playlist",
  "description": "Auto-generated",
  "items": ["song1.wav", "song2.wav"],
  "privacy": "PUBLIC",
  "mode": "mbf",
  "header_comment": "Optional"
}
```

### PlaylistCreateResponse
```json
{
  "playlist_id": "PL...",
  "playlist_url": "https://music.youtube.com/playlist?list=...",
  "created_count": 10,
  "skipped_count": 0,
  "unresolved_items": []
}
```

### CommentCreateRequest
```json
{
  "comment": "Nice playlist"
}
```

### YouTubeRegisterRequest
```json
{
  "urls": [
    "https://youtube.com/watch?v=...",
    "https://youtube.com/playlist?list=..."
  ]
}
```

### YouTubeRegisterResponse
```json
{
  "total": 2,
  "channel_success": 0,
  "channel_failed": 0,
  "video_success": 1,
  "video_failed": 0,
  "playlist_success": 1,
  "playlist_failed": 0,
  "details": [
    { "type": "video", "url": "...", "success": true, "message": "ok" }
  ]
}
```

### SongAdminDeleteRequest
```json
{
  "song_ids": ["song1.wav", "song2.wav"]
}
```

### SongAdminExcludeRequest
```json
{
  "song_ids": ["song1.wav", "song2.wav"],
  "excluded": true
}
```

## Async Job DTOs

### JobCreateRequest
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

### JobStatus
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

### JobResult (Similarity)
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

### JobResult (Segment)
```json
{
  "type": "segment_search",
  "result": {
    "items": [
      {
        "song": { "...": "SongSummary" },
        "score": 82.5,
        "hit_count": 12,
        "coverage": 0.64,
        "density": 0.18
      }
    ]
  }
}
```

### JobResult (Chain)
```json
{
  "type": "chain_search",
  "result": {
    "items": [
      { "seq": 1, "song": { "...": "SongSummary" }, "distance_or_score": 0.0 }
    ]
  }
}
```
