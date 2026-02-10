"use client";

import { useMemo, useState } from "react";
import { SongSummary } from "@/types/api";

const numberFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

type Props = {
  songs: SongSummary[];
};

export function SongSearchClient({ songs }: Props) {
  const [keyword, setKeyword] = useState("");

  const results = useMemo(() => {
    const key = keyword.trim().toLowerCase();
    if (!key) return songs;
    return songs.filter(
      (song) =>
        song.song_title.toLowerCase().includes(key) ||
        song.artist_name.toLowerCase().includes(key) ||
        song.song_id.toLowerCase().includes(key)
    );
  }, [keyword, songs]);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6">
        <label className="flex flex-col gap-2 text-sm text-slate-200">
          キーワード
          <input
            className="rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-base text-white focus:border-cyan-400 focus:outline-none"
            placeholder="曲名・アーティスト・動画IDなど"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </label>
        <p className="mt-3 text-xs text-slate-400">
          全{songs.length}件中{results.length}件を表示中。
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {results.map((song) => (
          <article
            key={song.song_id}
            className="rounded-2xl border border-white/10 bg-slate-900/60 p-5 shadow-lg shadow-black/20"
          >
            <header className="flex flex-col gap-1">
              <p className="text-xs uppercase tracking-wide text-cyan-300">
                BPM {song.bpm}
              </p>
              <h3 className="text-lg font-semibold text-white">{song.song_title}</h3>
              <p className="text-sm text-slate-300">{song.artist_name}</p>
            </header>
            <dl className="mt-4 grid grid-cols-2 gap-2 text-sm text-slate-300">
              <div>
                <dt className="text-xs text-slate-400">ソースディレクトリ</dt>
                <dd>{song.source_dir}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">ファイルサイズ</dt>
                <dd>{numberFormatter.format(song.file_size_mb)} MB</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">拡張子</dt>
                <dd>{song.file_extension}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">YouTube ID</dt>
                <dd className="font-mono text-xs">{song.youtube_id}</dd>
              </div>
            </dl>
            <p className="mt-4 text-xs text-slate-500">
              登録日: {new Date(song.registered_at).toLocaleDateString()}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
