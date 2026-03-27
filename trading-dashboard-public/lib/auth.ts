import type { AuthOptions } from 'next-auth';
import { getServerSession } from 'next-auth';
import { NextResponse } from 'next/server';
import CredentialsProvider from 'next-auth/providers/credentials';
import GoogleProvider from 'next-auth/providers/google';
import FacebookProvider from 'next-auth/providers/facebook';
import AppleProvider from 'next-auth/providers/apple';
import { PrismaAdapter } from '@next-auth/prisma-adapter';
import { prisma } from './prisma';
import { compare } from 'bcryptjs';

export const authOptions: AuthOptions = {
  // Only use PrismaAdapter when DATABASE_URL is properly configured.
  // In local dev with bootstrap admin, fall back to pure JWT sessions.
  adapter: process.env.DATABASE_URL?.includes('dummy') ? undefined : PrismaAdapter(prisma),
  providers: [
    // Email/password via CredentialsProvider (backed by Prisma User.passwordHash).
    CredentialsProvider({
      name: 'Email',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const email = credentials?.email?.toLowerCase().trim();
        const password = credentials?.password;

        if (!email || !password) {
          return null;
        }

        // Bootstrap admin path: allow a hardcoded admin login from .env for local dev.
        // This bypasses the database and email verification requirement.
        const adminEmail = process.env.ADMIN_EMAIL?.toLowerCase().trim();
        const adminPassword = process.env.ADMIN_PASSWORD;

        if (adminEmail && adminPassword && email === adminEmail && password === adminPassword) {
          return {
            id: 'bootstrap-admin',
            name: 'Bootstrap Admin',
            email: adminEmail,
            role: 'admin',
          };
        }

        const user = await prisma.user.findUnique({
          where: { email },
        });

        if (!user || !user.passwordHash) {
          return null;
        }

        const valid = await compare(password, user.passwordHash);
        if (!valid) {
          return null;
        }

        // Block login if email has not been verified yet.
        if (!user.emailVerified) {
          return null;
        }

        return {
          id: user.id,
          name: user.name ?? null,
          email: user.email ?? null,
          role: user.role,
        };
      },
    }),
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? '',
    }),
    FacebookProvider({
      clientId: process.env.FACEBOOK_CLIENT_ID ?? '',
      clientSecret: process.env.FACEBOOK_CLIENT_SECRET ?? '',
    }),
    AppleProvider({
      clientId: process.env.APPLE_CLIENT_ID ?? '',
      clientSecret: process.env.APPLE_CLIENT_SECRET ?? '',
    }),
  ],
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30 days
    updateAge: 24 * 60 * 60, // refresh token once per day
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        const u = user as { id?: string; role?: string };
        token.id = u.id;
        if (u.role) {
          (token as { role?: string }).role = u.role;
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user && token.id) {
        const s = session.user as { id?: string; role?: string };
        s.id = token.id as string;
        if ((token as { role?: string }).role) {
          s.role = (token as { role?: string }).role;
        }
      }
      return session;
    },
  },
};

export async function requireAuth(): Promise<NextResponse | null> {
  const session = await getServerSession(authOptions);
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  return null;
}
