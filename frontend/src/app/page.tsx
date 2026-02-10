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
          ステータス、カタログ参照、プレイリスト履歴を一望できます。FastAPI 製バックエンドと
          直接連携しており、API ドキュメントの DTO と同じ構造でデータを受け取るため、UI 側は
          追加実装なしで本番データに差し替わります。
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
            <ListBlock
              title="Most referenced songs"
              rows={playlistStats.top_songs.map((song) => ({
                label: song.song_id,
                value: song.count,
              }))}
            />
            <ListBlock
              title="Top artists"
              rows={playlistStats.top_artists.map((artist) => ({
                label: artist.artist_name,
                value: artist.count,
              }))}
            />
            <ListBlock
              title="Popular starters"
              rows={playlistStats.top_start_songs.map((song) => ({
                label: song.song_id,
                value: song.count,
              }))}
            />
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

type RankingRow = {
  label: string;
  value: string | number;
};

type ListBlockProps = {
  title: string;
  rows: RankingRow[];
};

function ListBlock({ title, rows }: ListBlockProps) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{title}</p>
      <div className="mt-3 overflow-hidden rounded-xl border border-white/5">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="w-16 px-4 py-2 text-left font-semibold">#</th>
              <th className="px-4 py-2 text-left font-semibold">Name</th>
              <th className="w-24 px-4 py-2 text-right font-semibold">Count</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.label}-${index}`} className="odd:bg-slate-900/40">
                <td className="px-4 py-2 font-mono text-xs text-slate-500">
                  {String(index + 1).padStart(2, "0")}
                </td>
                <td className="px-4 py-2 text-slate-100">{row.label}</td>
                <td className="px-4 py-2 text-right text-base font-semibold text-slate-200">
                  {row.value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
