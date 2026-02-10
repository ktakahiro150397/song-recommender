import { SongSearchClient } from "@/components/song-search-client";
import { searchSongs } from "@/lib/api-client";

export const metadata = {
  title: "楽曲検索 | Song Recommender",
};

export default async function SongsPage() {
  const { data: songs } = await searchSongs();

  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-8">
        <p className="text-sm uppercase tracking-[0.3em] text-cyan-300">
          楽曲検索
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-white">
          埋め込みと類似曲をざっくり確認
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-300">
          MVPの要件通り、登録済み楽曲に対するキーワード検索と簡易メタデータ表示に絞っています。
          BPM・保管ディレクトリ・元動画IDなどの情報をすぐ確認でき、将来的には類似検索やチェイン検索、
          プレイリスト生成ボタンをこの画面に段階的に追加していく想定です。
        </p>
      </section>

      <SongSearchClient songs={songs} />
    </div>
  );
}
