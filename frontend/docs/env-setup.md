# Environment Setup (NextAuth + Google API)

This document lists required environment variables and Google Cloud settings.

## Google Cloud Console
1) Enable APIs
- YouTube Data API v3

2) OAuth consent screen
- App name, support email, scopes
- Add privacy policy URL (required for external apps)

3) OAuth client (Web)
- Authorized redirect URI
  - Production: https://your-domain/api/auth/callback/google
  - Local: http://localhost:3000/api/auth/callback/google

## Next.js (.env.local)
Create .env.local in the Next.js project root:
```
NEXTAUTH_URL=https://your-domain
NEXTAUTH_SECRET=your-secret
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## NextAuth Scopes
- https://www.googleapis.com/auth/youtube

If you need refresh tokens:
- access_type=offline
- prompt=consent

## API Server (.env)
```
ADMIN_EMAILS=admin@example.com
ADMIN_SUBS=
JWT_ISSUER=your-issuer
JWT_AUDIENCE=your-audience
```

## Notes
- Keep secrets out of git.
- Use different OAuth clients for local and production if needed.

---

## NextAuth Config Example (App Router)
Create src/app/api/auth/[...nextauth]/route.ts
```ts
import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
      authorization: {
        params: {
          scope: "openid email profile https://www.googleapis.com/auth/youtube",
          access_type: "offline",
          prompt: "consent",
        },
      },
    }),
  ],
  secret: process.env.NEXTAUTH_SECRET,
  callbacks: {
    async jwt({ token, account }) {
      if (account?.access_token) {
        token.accessToken = account.access_token;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.accessToken = token.accessToken as string | undefined;
      }
      return session;
    },
  },
});

export { handler as GET, handler as POST };
```
