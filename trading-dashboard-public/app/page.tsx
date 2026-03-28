import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { getServerSession } from 'next-auth';
import { authOptions } from '../lib/auth';
import LandingPage from './landing/page';

export const metadata: Metadata = {
  title: 'You know how to trade. Winzinvest keeps you out of your own way.',
  description:
    'Winzinvest automates equity momentum and options premium strategies through Interactive Brokers, enforcing 13 execution checks on every order so your rules are followed without exception.',
};

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function Home(props: PageProps) {
  if (props.params) await props.params;
  if (props.searchParams) await props.searchParams;

  // getServerSession throws if NEXTAUTH_SECRET is missing — catch only that,
  // not the NEXT_REDIRECT thrown by redirect() itself.
  let session = null;
  try {
    session = await getServerSession(authOptions);
  } catch {
    // Missing NEXTAUTH_SECRET — fall through and render landing page
  }

  // Authenticated users go straight to the dashboard
  if (session) {
    redirect('/dashboard');
  }

  // Public visitors see the landing page at / (not a redirect — URL stays winzinvest.com)
  return <LandingPage />;
}
