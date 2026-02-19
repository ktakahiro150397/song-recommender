export type ResponseMeta = {
  request_id: string
  total?: number
  limit?: number
  offset?: number
}

export type ApiError = {
  code: string
  message: string
  details?: Record<string, unknown> | null
}

export type ResponseEnvelope<T> = {
  data: T
  error: ApiError | null
  meta?: ResponseMeta | null
}

export type UserProfile = {
  sub: string
  email: string
  name: string
  alias?: string | null
  picture?: string | null
  is_admin: boolean
}

export type SongSummary = {
  song_id: string
  song_title: string
  artist_name: string
  source_dir: string
  bpm: number
  youtube_id: string
  file_extension: string
  file_size_mb: number
  registered_at: string
  excluded_from_search: boolean
}

export type SimilarSongItem = {
  song: SongSummary
  distance: number
}

export type SegmentSimilarItem = {
  song: SongSummary
  score: number
  hit_count: number
  coverage: number
  density: number
}

export type ChainSearchItem = {
  seq: number
  song: SongSummary
  distance_or_score: number
}

export type PlaylistHeader = {
  playlist_id: string
  playlist_name: string
  playlist_url: string
  creator_sub: string
  creator_display_name: string
  created_at: string
  header_comment?: string | null
}

export type PlaylistItem = {
  seq: number
  song_id: string
  cosine_distance: number
  source_dir: string
}

export type PlaylistComment = {
  id: number
  playlist_id: string
  user_sub: string
  display_name: string
  comment: string
  is_deleted: boolean
  created_at: string
}

export type PlaylistHistoryEntry = {
  header: PlaylistHeader
  items: PlaylistItem[]
  comments: PlaylistComment[]
}

export type PlaylistCreatePrivacy = 'PUBLIC' | 'UNLISTED' | 'PRIVATE'

export type PlaylistCreateRequest = {
  name: string
  description?: string
  items: string[]
  privacy?: PlaylistCreatePrivacy
  mode?: string
  header_comment?: string
}

export type PlaylistCreateResponse = {
  playlist_id: string
  playlist_url: string
  created_count: number
  skipped_count: number
  unresolved_items: string[]
}

export type ChannelItem = {
  id: number
  channel_id: string
  channel_name: string
  url: string
  thumbnail_url: string
  registered_at: string
}

export type SongQueueItem = {
  id: number
  video_id: string
  url: string
  title: string
  artist_name: string
  status: 'pending' | 'processed' | 'failed'
  registered_at: string
}

export type StatsOverview = {
  total_songs: number
  total_channels: number
  queue_counts: {
    pending: number
    processed: number
    failed: number
    total: number
  }
  total_size_gb: number
}

export type StatsPlaylists = {
  top_songs: Array<{ song_id: string; count: number }>
  top_artists: Array<{ artist_name: string; count: number }>
  top_start_songs: Array<{ song_id: string; count: number }>
}

export type DbCollectionCounts = {
  full: number
  balance: number
  minimal: number
  seg_mert: number
  seg_ast: number
}
