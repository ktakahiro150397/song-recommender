import { getDbCollectionCounts, getStatsOverview, getStatsPlaylists } from "@/lib/api-client";

const numberFormatter = new Intl.NumberFormat("en-US");

const storageFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const queueLabelMap: Record<string, string> = {
  pending: "Pending",
  processed: "Processed",
  failed: "Failed",
  total: "Total",
};

const dbLabelMap: Record<string, string> = {
  full: "Full Collection",
  balance: "Balance Collection",
  minimal: "Minimal Collection",
  seg_mert: "Seg (MERT)",
  seg_ast: "Seg (AST)",
};

export default async function HomePage() {
  const [overviewResponse, playlistResponse, dbCountsResponse] = await Promise.all([
    getStatsOverview(),
    getStatsPlaylists(),
    getDbCollectionCounts(),
  ]);

  const overview = overviewResponse.data;
  const playlistStats = playlistResponse.data;
  const dbCounts = dbCountsResponse.data;

  return (
    <div className="space-y-10">
      <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-8 shadow-2xl shadow-black/40">
        <p className="text-sm uppercase tracking-[0.3em] text-cyan-300">
          MVP・フェーズ1
        </p>
        <h1 className="mt-4 text-4xl font-semibold text-white">
          Song Recommender コントロールルーム
        </h1>
        <p className="mt-4 max-w-3xl text-base text-slate-300">
          このダッシュボードでは移行計画に記載された「公開・閲覧専用」範囲にフォーカスし、
          ステータス、カタログ参照、プレイリスト履歴を一望できます。現在はモックデータですが、
          APIドキュメントのDTOと同じ構造を保っているため、実際のエンドポイントに差し替えても
          レイアウトを変える必要がありません。
        </p>
      </section>

      <section className="space-y-4">
        <header className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-cyan-300">
              Overview
            </p>
            <h2 className="text-2xl font-semibold text-white">Library pulse</h2>
          </div>
        </header>
        <div className="grid gap-4 md:grid-cols-4">
          <div className="dashboard-card">
            <p className="card-label">Total songs</p>
            <p className="card-value">
              {numberFormatter.format(overview.total_songs)}
            </p>
          </div>
          <div className="dashboard-card">
            <p className="card-label">Total channels</p>
            <p className="card-value">
              {numberFormatter.format(overview.total_channels)}
            </p>
          </div>
          <div className="dashboard-card">
            <p className="card-label">Storage footprint</p>
            <p className="card-value">
              {storageFormatter.format(overview.total_size_gb)} GB
            </p>
          </div>
          <div className="dashboard-card">
            <p className="card-label">Queue total</p>
            <p className="card-value">
              {numberFormatter.format(overview.queue_counts.total)}
            </p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {Object.entries(overview.queue_counts).map(([key, value]) => (
            <div key={key} className="rounded-2xl border border-white/10 bg-slate-900/60 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-400">
                Queue · {queueLabelMap[key] ?? key}
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {numberFormatter.format(value)}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-8 lg:grid-cols-2">
        <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-6">
          <p className="text-xs uppercase tracking-[0.4em] text-pink-300">
            Playlists
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">
            Top performers
          </h2>
          <div className="mt-4 space-y-4">
            <ListBlock title="Most referenced songs">
              {playlistStats.top_songs.map((song) => (
                <li key={song.song_id}>
                  <span>{song.song_id}</span>
                  <span>{song.count}</span>
                </li>
              ))}
            </ListBlock>
            <ListBlock title="Top artists">
              {playlistStats.top_artists.map((artist) => (
                <li key={artist.artist_name}>
                  <span>{artist.artist_name}</span>
                  <span>{artist.count}</span>
                </li>
              ))}
            </ListBlock>
            <ListBlock title="Popular starters">
              {playlistStats.top_start_songs.map((song) => (
                <li key={song.song_id}>
                  <span>{song.song_id}</span>
                  <span>{song.count}</span>
                </li>
              ))}
            </ListBlock>
          </div>
        </div>
        <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-6">
          <p className="text-xs uppercase tracking-[0.4em] text-amber-300">
            Embedding DB
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">Collection coverage</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {Object.entries(dbCounts).map(([key, value]) => (
              <div key={key} className="rounded-2xl border border-white/10 bg-slate-900/80 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-400">
                  {dbLabelMap[key] ?? key}
                </p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {numberFormatter.format(value)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

type ListBlockProps = {
  title: string;
  children: React.ReactNode;
};

function ListBlock({ title, children }: ListBlockProps) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      <ul className="mt-3 space-y-2 text-sm text-slate-200">
        {children}
      </ul>
    </div>
  );
}
