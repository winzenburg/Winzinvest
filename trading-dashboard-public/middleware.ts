import { withAuth } from 'next-auth/middleware';
import { NextResponse } from 'next/server';

export default withAuth(
  function middleware(req) {
    // Allow the request through — withAuth already validated the token
    return NextResponse.next();
  },
  {
    callbacks: {
      authorized({ token }) {
        return !!token;
      },
    },
    pages: {
      signIn: '/login',
    },
  },
);

// Protect page routes only. All `/api/*` routes are excluded here — each handler
// uses requireAuth() and returns JSON 401. Running withAuth on API routes can
// redirect unauthenticated fetches to /login (HTML), which breaks client
// fetch().json() and causes confusing "Failed to fetch" in some cases.
// (.+) requires at least one char after `/` so the bare root `/` is excluded
export const config = {
  matcher: [
    '/((?!login|landing|strategy|methodology|performance|research|overview|api/|_next/static|_next/image|favicon.ico).+)',
  ],
};
