/**
 * API クライアント
 *
 * FastAPI バックエンドへのリクエストをラップする関数群。
 * サーバーサイド・クライアントサイド両方から呼び出せるよう
 * fetch() ベースで実装している。
 *
 * バックエンドの URL は環境変数 NEXT_PUBLIC_API_BASE_URL または
 * API_BASE_URL（サーバーサイド専用）で設定する。
 * 未設定時は http://localhost:8000 にフォールバックする。
 */

import type {
  DbCollectionCounts,
  PlaylistCreateRequest,
  PlaylistCreateResponse,
  PlaylistHistoryEntry,
  ResponseEnvelope,
  SegmentSimilarItem,
  SimilarSongItem,
  SongSummary,
  StatsOverview,
  StatsPlaylists,
} from "@/types/api";

function getApiBase(): string {
  // サーバーサイドでは非公開環境変数を優先
  if (typeof window === "undefined") {
    return process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<ResponseEnvelope<T>> {
  const url = `${getApiBase()}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    // サーバーサイドでキャッシュしない（常に最新を取得）
    cache: init?.cache ?? "no-store",
  });

  if (!res.ok) {
    let message = `API error: ${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) message = String(body.detail);
    } catch {
      // ignore parse errors
    }
    return {
      data: null as T,
      error: { code: String(res.status), message },
      meta: null,
    };
  }

  return res.json() as Promise<ResponseEnvelope<T>>;
}

// ────────────────────────────────────────────────────────────────────────────
// 統計情報
// ────────────────────────────────────────────────────────────────────────────

export async function getStatsOverview(): Promise<ResponseEnvelope<StatsOverview>> {
  return apiFetch<StatsOverview>("/api/stats/overview");
}

export async function getStatsPlaylists(): Promise<ResponseEnvelope<StatsPlaylists>> {
  return apiFetch<StatsPlaylists>("/api/stats/playlists");
}

export async function getDbCollectionCounts(): Promise<ResponseEnvelope<DbCollectionCounts>> {
  return apiFetch<DbCollectionCounts>("/api/stats/db-collections");
}

// ────────────────────────────────────────────────────────────────────────────
// 楽曲
// ────────────────────────────────────────────────────────────────────────────

export async function searchSongs(params: {
  keyword?: string;
  limit?: number;
  offset?: number;
}): Promise<ResponseEnvelope<SongSummary[]>> {
  const query = new URLSearchParams();
  if (params.keyword) query.set("keyword", params.keyword);
  if (params.limit != null) query.set("limit", String(params.limit));
  if (params.offset != null) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiFetch<SongSummary[]>(`/api/songs${qs ? `?${qs}` : ""}`);
}

export async function getSimilarSongs(
  songId: string,
  params: { db?: string; nResults?: number }
): Promise<ResponseEnvelope<SimilarSongItem[]>> {
  const query = new URLSearchParams();
  if (params.db) query.set("db", params.db);
  if (params.nResults != null) query.set("n_results", String(params.nResults));
  const qs = query.toString();
  return apiFetch<SimilarSongItem[]>(
    `/api/songs/${encodeURIComponent(songId)}/similar${qs ? `?${qs}` : ""}`
  );
}

export async function getSimilarSegments(
  songId: string,
  params: { collection?: string; nResults?: number }
): Promise<ResponseEnvelope<SegmentSimilarItem[]>> {
  const query = new URLSearchParams();
  if (params.collection) query.set("collection", params.collection);
  if (params.nResults != null) query.set("n_results", String(params.nResults));
  const qs = query.toString();
  return apiFetch<SegmentSimilarItem[]>(
    `/api/songs/${encodeURIComponent(songId)}/similar-segments${qs ? `?${qs}` : ""}`
  );
}

// ────────────────────────────────────────────────────────────────────────────
// プレイリスト
// ────────────────────────────────────────────────────────────────────────────

export async function getPlaylistHistory(): Promise<ResponseEnvelope<PlaylistHistoryEntry[]>> {
  return apiFetch<PlaylistHistoryEntry[]>("/api/playlists/history");
}

export async function createPlaylist(
  body: PlaylistCreateRequest
): Promise<ResponseEnvelope<PlaylistCreateResponse>> {
  return apiFetch<PlaylistCreateResponse>("/api/playlists/create", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
