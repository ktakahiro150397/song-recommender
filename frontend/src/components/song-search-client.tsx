"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getSimilarSegments, getSimilarSongs, searchSongs } from "@/lib/api-client";
import { SegmentSimilarItem, SimilarSongItem, SongSummary } from "@/types/api";

const distanceFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});

const bpmFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const scoreFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const ratioFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

type SimilarDb = "full" | "balance" | "minimal";
type SegmentCollection = "mert" | "ast";

const dbOptions: { value: SimilarDb; label: string }[] = [
  { value: "full", label: "Full" },
  { value: "balance", label: "Balance" },
  { value: "minimal", label: "Minimal" },
];

const limitOptions = [5, 10, 15, 20];
const segmentCollections: { value: SegmentCollection; label: string }[] = [
  { value: "mert", label: "MERT" },
  { value: "ast", label: "AST" },
];
const PAGE_SIZE = 30;
const SEARCH_DEBOUNCE_MS = 300;

export function SongSearchClient() {
  const [keyword, setKeyword] = useState("");
  const [songs, setSongs] = useState<SongSummary[]>([]);
  const [totalSongs, setTotalSongs] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingSongs, setIsLoadingSongs] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [songsError, setSongsError] = useState<string | null>(null);
  const [selectedSong, setSelectedSong] = useState<SongSummary | null>(null);
  const [similarDb, setSimilarDb] = useState<SimilarDb>("full");
  const [similarLimit, setSimilarLimit] = useState(10);
  const [similarSongs, setSimilarSongs] = useState<SimilarSongItem[]>([]);
  const [isLoadingSimilar, setIsLoadingSimilar] = useState(false);
  const [similarError, setSimilarError] = useState<string | null>(null);
  const [segmentCollection, setSegmentCollection] =
    useState<SegmentCollection>("mert");
  const [segmentLimit, setSegmentLimit] = useState(10);
  const [segmentResults, setSegmentResults] = useState<SegmentSimilarItem[]>([]);
  const [isLoadingSegments, setIsLoadingSegments] = useState(false);
  const [segmentError, setSegmentError] = useState<string | null>(null);
  const loadIdRef = useRef(0);
  const offsetRef = useRef(0);
  const totalRef = useRef<number | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const loadSongs = useCallback(
    async ({ reset, query }: { reset: boolean; query: string }) => {
      const currentOffset = reset ? 0 : offsetRef.current;
      const requestId = ++loadIdRef.current;

      if (reset) {
        setIsLoadingSongs(true);
        setIsLoadingMore(false);
        setSongsError(null);
        setSongs([]);
        setOffset(0);
        offsetRef.current = 0;
        setHasMore(true);
        setTotalSongs(null);
        totalRef.current = null;
        setSelectedSong(null);
      } else {
        setIsLoadingMore(true);
        setSongsError(null);
      }

      try {
        const response = await searchSongs({
          keyword: query,
          limit: PAGE_SIZE,
          offset: currentOffset,
        });

        if (requestId !== loadIdRef.current) return;
        if (response.error) {
          setSongsError(response.error.message);
          return;
        }

        const data = response.data ?? [];
        const meta = response.meta ?? undefined;
        const resolvedTotal =
          typeof meta?.total === "number"
            ? meta.total
            : reset
            ? data.length
            : totalRef.current ?? currentOffset + data.length;

        setSongs((prev) => (reset ? data : [...prev, ...data]));
        setTotalSongs(resolvedTotal);
        totalRef.current = resolvedTotal;
        const nextOffset = currentOffset + data.length;
        setOffset(nextOffset);
        offsetRef.current = nextOffset;
        setHasMore(
          typeof meta?.total === "number"
            ? nextOffset < meta.total
            : data.length === PAGE_SIZE
        );
        if (reset && data.length === 0) {
          setHasMore(false);
        }
      } catch (error: unknown) {
        if (requestId !== loadIdRef.current) return;
        const message =
          error instanceof Error ? error.message : "楽曲の取得に失敗しました";
        setSongsError(message);
        setHasMore(false);
      } finally {
        if (requestId === loadIdRef.current) {
          setIsLoadingSongs(false);
          setIsLoadingMore(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    const trimmed = keyword.trim();
    const timer = window.setTimeout(() => {
      loadSongs({ reset: true, query: trimmed });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [keyword, loadSongs]);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;
    if (!hasMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) return;
        if (isLoadingSongs || isLoadingMore) return;
        loadSongs({ reset: false, query: keyword.trim() });
      },
      { rootMargin: "200px" }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, isLoadingSongs, keyword, loadSongs]);

  useEffect(() => {
    if (!selectedSong) return;
    let canceled = false;
    setIsLoadingSimilar(true);
    setSimilarSongs([]);
    setSimilarError(null);

    getSimilarSongs(selectedSong.song_id, {
      db: similarDb,
      nResults: similarLimit,
    })
      .then((response) => {
        if (canceled) return;
        if (response.error) {
          setSimilarError(response.error.message);
          setSimilarSongs([]);
          return;
        }
        setSimilarSongs(response.data ?? []);
      })
      .catch((error: unknown) => {
        if (canceled) return;
        const message =
          error instanceof Error ? error.message : "類似曲の取得に失敗しました";
        setSimilarError(message);
        setSimilarSongs([]);
      })
      .finally(() => {
        if (!canceled) {
          setIsLoadingSimilar(false);
        }
      });

    return () => {
      canceled = true;
    };
  }, [selectedSong, similarDb, similarLimit]);

  useEffect(() => {
    if (!selectedSong) return;
    let canceled = false;
    setIsLoadingSegments(true);
    setSegmentResults([]);
    setSegmentError(null);

    getSimilarSegments(selectedSong.song_id, {
      collection: segmentCollection,
      nResults: segmentLimit,
    })
      .then((response) => {
        if (canceled) return;
        if (response.error) {
          setSegmentError(response.error.message);
          setSegmentResults([]);
          return;
        }
        setSegmentResults(response.data ?? []);
      })
      .catch((error: unknown) => {
        if (canceled) return;
        const message =
          error instanceof Error
            ? error.message
            : "セグメント類似曲の取得に失敗しました";
        setSegmentError(message);
        setSegmentResults([]);
      })
      .finally(() => {
        if (!canceled) {
          setIsLoadingSegments(false);
        }
      });

    return () => {
      canceled = true;
    };
  }, [selectedSong, segmentCollection, segmentLimit]);

  const totalLabel = totalSongs ?? songs.length;
  const countLabel = keyword.trim()
    ? `検索結果 ${totalLabel}件中${songs.length}件を表示中。`
    : `全${totalLabel}件中${songs.length}件を表示中。`;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
        <label className="flex flex-col gap-2 text-sm text-slate-200">
          キーワード
          <input
            className="rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-base text-white focus:border-cyan-400 focus:outline-none"
            placeholder="曲名・アーティストで検索"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </label>
        <p className="mt-3 text-xs text-slate-400">{countLabel}</p>
        {songsError ? (
          <p className="mt-2 text-xs text-rose-300">{songsError}</p>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">楽曲</th>
              <th className="px-4 py-3 text-left font-semibold">アーティスト</th>
              <th className="w-20 px-4 py-3 text-left font-semibold">BPM</th>
              <th className="w-32 px-4 py-3 text-left font-semibold">登録日</th>
              <th className="w-32 px-4 py-3 text-left font-semibold">操作</th>
            </tr>
          </thead>
          <tbody>
            {songs.map((song) => (
              <tr key={song.song_id} className="odd:bg-slate-900/40">
                <td className="px-4 py-3 text-slate-100">
                  {song.youtube_id ? (
                    <a
                      className="font-semibold text-cyan-200 underline decoration-cyan-300 underline-offset-4 hover:text-cyan-100"
                      href={`https://music.youtube.com/watch?v=${encodeURIComponent(
                        song.youtube_id
                      )}`}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {song.song_title}
                    </a>
                  ) : (
                    song.song_title
                  )}
                </td>
                <td className="px-4 py-3 text-slate-300">{song.artist_name}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-300">
                  {typeof song.bpm === "number"
                    ? bpmFormatter.format(song.bpm)
                    : "-"}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {new Date(song.registered_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <button
                    className={`w-full rounded-lg border px-3 py-2 text-xs font-medium transition ${
                      selectedSong?.song_id === song.song_id
                        ? "border-cyan-400 bg-cyan-400/10 text-cyan-100"
                        : "border-white/15 text-slate-200 hover:border-cyan-400 hover:text-cyan-200"
                    }`}
                    onClick={() => setSelectedSong({ ...song })}
                  >
                    類似曲を検索
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {isLoadingSongs ? (
        <p className="text-sm text-slate-300">検索中...</p>
      ) : songs.length === 0 ? (
        <p className="text-sm text-slate-400">該当する楽曲がありません。</p>
      ) : null}

      <div ref={sentinelRef} aria-hidden="true" />

      {isLoadingMore ? (
        <p className="text-sm text-slate-400">続きを読み込み中...</p>
      ) : hasMore ? null : (
        <p className="text-sm text-slate-500">これ以上の楽曲はありません。</p>
      )}

      <section className="space-y-6 rounded-3xl border border-white/10 bg-slate-900/60 p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1">
            <p className="text-xs uppercase tracking-[0.4em] text-pink-300">
              Similarity Search
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-white">類似曲検索</h2>
            <p className="mt-2 text-sm text-slate-300">
              任意の曲カードで「類似曲を検索」を押すと、このセクションに結果が表示されます。
              DB と件数を切り替えると自動で再検索します。
            </p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm text-slate-200">
            <label className="flex flex-col gap-1">
              コレクション
              <select
                className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-white"
                value={similarDb}
                onChange={(event) =>
                  setSimilarDb(event.target.value as SimilarDb)
                }
              >
                {dbOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              件数
              <select
                className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-white"
                value={similarLimit}
                onChange={(event) => setSimilarLimit(Number(event.target.value))}
              >
                {limitOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {selectedSong ? (
          <div className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-xs uppercase tracking-wide text-cyan-300">
                Query Song
              </p>
              <h3 className="text-xl font-semibold text-white">
                {selectedSong.song_title}
              </h3>
              <p className="text-sm text-slate-300">
                {selectedSong.artist_name}
              </p>
              <p className="mt-2 text-xs text-slate-400">
                {selectedSong.song_id} / BPM{" "}
                {typeof selectedSong.bpm === "number"
                  ? bpmFormatter.format(selectedSong.bpm)
                  : "-"}
              </p>
            </div>
            <div>
              {isLoadingSimilar ? (
                <p className="text-sm text-slate-300">検索中...</p>
              ) : similarError ? (
                <p className="text-sm text-rose-300">{similarError}</p>
              ) : similarSongs.length ? (
                <SimilarResultsTable items={similarSongs} />
              ) : (
                <p className="text-sm text-slate-400">
                  類似曲が見つかりませんでした。
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-400">
            楽曲カードのボタンから検索対象を選ぶと、ここにランキングで表示されます。
          </p>
        )}
      </section>

      <section className="space-y-6 rounded-3xl border border-white/10 bg-slate-900/60 p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1">
            <p className="text-xs uppercase tracking-[0.4em] text-amber-300">
              Segment Similarity
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-white">
              セグメント類似検索 (MERT / AST)
            </h2>
            <p className="mt-2 text-sm text-slate-300">
              MERT/AST のセグメント特徴量から近い曲を集計します。
            </p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm text-slate-200">
            <label className="flex flex-col gap-1">
              コレクション
              <select
                className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-white"
                value={segmentCollection}
                onChange={(event) =>
                  setSegmentCollection(event.target.value as SegmentCollection)
                }
              >
                {segmentCollections.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              件数
              <select
                className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-white"
                value={segmentLimit}
                onChange={(event) => setSegmentLimit(Number(event.target.value))}
              >
                {limitOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {selectedSong ? (
          <div className="space-y-4">
            <div>
              {isLoadingSegments ? (
                <p className="text-sm text-slate-300">検索中...</p>
              ) : segmentError ? (
                <p className="text-sm text-rose-300">{segmentError}</p>
              ) : segmentResults.length ? (
                <SegmentResultsTable items={segmentResults} />
              ) : (
                <p className="text-sm text-slate-400">
                  セグメント類似曲が見つかりませんでした。
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-400">
            楽曲カードのボタンから検索対象を選ぶと、ここにランキングで表示されます。
          </p>
        )}
      </section>
    </div>
  );
}

type SimilarResultsTableProps = {
  items: SimilarSongItem[];
};

function SimilarResultsTable({ items }: SimilarResultsTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="w-16 px-4 py-2 text-left font-semibold">#</th>
            <th className="px-4 py-2 text-left font-semibold">楽曲</th>
            <th className="px-4 py-2 text-left font-semibold">アーティスト</th>
            <th className="px-4 py-2 text-left font-semibold">Source Dir</th>
            <th className="w-28 px-4 py-2 text-right font-semibold">Distance</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={item.song.song_id} className="odd:bg-slate-900/40">
              <td className="px-4 py-2 font-mono text-xs text-slate-500">
                {String(index + 1).padStart(2, "0")}
              </td>
              <td className="px-4 py-2 text-slate-100">
                {item.song.song_title}
              </td>
              <td className="px-4 py-2 text-slate-300">
                {item.song.artist_name}
              </td>
              <td className="px-4 py-2 text-slate-400">
                {item.song.source_dir}
              </td>
              <td className="px-4 py-2 text-right font-mono text-sm text-slate-200">
                {distanceFormatter.format(item.distance)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type SegmentResultsTableProps = {
  items: SegmentSimilarItem[];
};

function SegmentResultsTable({ items }: SegmentResultsTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="w-16 px-4 py-2 text-left font-semibold">#</th>
            <th className="px-4 py-2 text-left font-semibold">楽曲</th>
            <th className="px-4 py-2 text-left font-semibold">アーティスト</th>
            <th className="px-4 py-2 text-left font-semibold">Source Dir</th>
            <th className="w-24 px-4 py-2 text-right font-semibold">Score</th>
            <th className="w-20 px-4 py-2 text-right font-semibold">Hits</th>
            <th className="w-24 px-4 py-2 text-right font-semibold">Coverage</th>
            <th className="w-24 px-4 py-2 text-right font-semibold">Density</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={item.song.song_id} className="odd:bg-slate-900/40">
              <td className="px-4 py-2 font-mono text-xs text-slate-500">
                {String(index + 1).padStart(2, "0")}
              </td>
              <td className="px-4 py-2 text-slate-100">
                {item.song.song_title}
              </td>
              <td className="px-4 py-2 text-slate-300">
                {item.song.artist_name}
              </td>
              <td className="px-4 py-2 text-slate-400">
                {item.song.source_dir}
              </td>
              <td className="px-4 py-2 text-right font-mono text-sm text-slate-200">
                {scoreFormatter.format(item.score)}
              </td>
              <td className="px-4 py-2 text-right font-mono text-sm text-slate-200">
                {item.hit_count}
              </td>
              <td className="px-4 py-2 text-right font-mono text-sm text-slate-200">
                {ratioFormatter.format(item.coverage * 100)}%
              </td>
              <td className="px-4 py-2 text-right font-mono text-sm text-slate-200">
                {ratioFormatter.format(item.density * 100)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
