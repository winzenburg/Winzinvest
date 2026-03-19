import type { AuthOptions } from 'next-auth';
import { getServerSession } from 'next-auth';
import { NextResponse } from 'next/server';
import CredentialsProvider from 'next-auth/providers/credentials';

export const authOptions: AuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'Winzinvest',
      credentials: {
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const expected = process.env.DASHBOARD_PASSWORD;
        if (!expected) {
          console.error('[auth] DASHBOARD_PASSWORD not set — all logins rejected');
          return null;
        }
        if (credentials?.password === expected) {
          return { id: '1', name: 'Operator', email: 'operator@missioncontrol' };
        }
        return null;
      },
    }),
  ],
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30 days
    updateAge: 24 * 60 * 60,   // refresh token once per day
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) token.id = user.id;
      return token;
    },
    async session({ session, token }) {
      if (session.user && token.id) {
        (session.user as { id?: string }).id = token.id as string;
      }
      return session;
    },
  },
};

/**
 * Call at the top of any API route handler to enforce authentication.
 * Returns a 401 NextResponse if the request is unauthenticated, or null
 * if the session is valid (caller should proceed).
 *
 * Usage:
 *   const unauth = await requireAuth();
 *   if (unauth) return unauth;
 */
export async function requireAuth(): Promise<NextResponse | null> {
  const session = await getServerSession(authOptions);
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  return null;
}
