import { PlaylistHistoryClient } from "@/components/playlist-history-client";
import { getPlaylistHistory } from "@/lib/api-client";

export const metadata = {
  title: "プレイリスト履歴 | Song Recommender",
};

export default async function PlaylistHistoryPage() {
  const { data: history } = await getPlaylistHistory();

  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-8">
        <p className="text-sm uppercase tracking-[0.3em] text-cyan-300">
          プレイリスト履歴
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-white">
          生成チェインとフィードバックのアーカイブ
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-300">
          MVPでは閲覧専用で、チェイン内容とコメントログを一覧できます。コメント投稿・削除や
          プレイリスト削除といった認証必須アクションは、ドキュメントで定義された保護エンドポイントに
          接続する形で後から差し込めるよう、同じデータ構造をそのまま利用しています。
        </p>
      </section>

      <PlaylistHistoryClient history={history} />
    </div>
  );
}
