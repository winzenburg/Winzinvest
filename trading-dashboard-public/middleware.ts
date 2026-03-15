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

// Protect everything except root, login, landing, strategy, auth API, and static assets
// (.+) requires at least one char after `/` so the bare root `/` is excluded
export const config = {
  matcher: [
    '/((?!login|landing|strategy|api/auth|_next/static|_next/image|favicon.ico).+)',
  ],
};
