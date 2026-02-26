import type { NextConfig } from "next";

const apiBase =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",

  // クライアントサイドから /api/* を叩いたとき FastAPI バックエンドに転送する。
  // サーバーサイドコンポーネントは api-client.ts の getApiBase() で直接フォールバックする。
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
