"use client";

import { PlaylistHistoryEntry } from "@/types/api";

type Props = {
  history: PlaylistHistoryEntry[];
};

export function PlaylistHistoryClient({ history }: Props) {
  return (
    <div className="space-y-4">
      {history.map((entry) => (
        <article
          key={entry.header.playlist_id}
          className="rounded-2xl border border-white/10 bg-slate-900/60 p-6"
        >
          <header className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-cyan-300">
                作成日 {new Date(entry.header.created_at).toLocaleDateString()}
              </p>
              <h3 className="text-xl font-semibold text-white">
                {entry.header.playlist_name}
              </h3>
              <p className="text-sm text-slate-300">
                作成者: {entry.header.creator_display_name}
              </p>
            </div>
            <a
              href={entry.header.playlist_url}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-cyan-400/60 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-400/10"
            >
              プレイリストを開く
            </a>
          </header>
          {entry.header.header_comment ? (
            <p className="mt-3 text-sm text-slate-300">
              {entry.header.header_comment}
            </p>
          ) : null}
          <div className="mt-4 grid gap-3 text-sm text-slate-200 md:grid-cols-2">
            {entry.items.map((item) => (
              <div
                key={`${entry.header.playlist_id}-${item.seq}`}
                className="rounded-xl border border-white/10 bg-slate-900/80 px-4 py-3"
              >
                <p className="text-xs text-slate-400">#{item.seq}</p>
                <p className="font-semibold">{item.song_id}</p>
                <p className="text-xs text-slate-400">
                  距離 {item.cosine_distance.toFixed(3)} / {item.source_dir}
                </p>
              </div>
            ))}
          </div>
          <footer className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <span>{entry.items.length} 件の楽曲</span>
            <span>•</span>
            <span>{entry.comments.length} 件のコメント</span>
          </footer>
        </article>
      ))}
    </div>
  );
}
