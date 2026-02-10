import Link from "next/link";

const navItems = [
  { href: "/", label: "ダッシュボード" },
  { href: "/songs", label: "楽曲検索" },
  { href: "/playlists", label: "プレイリスト履歴" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-white">
          Song Recommender
        </Link>
        <nav className="flex items-center gap-4 text-sm font-medium text-slate-300">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-full px-4 py-2 transition hover:bg-white/10 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
