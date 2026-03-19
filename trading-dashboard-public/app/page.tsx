import { redirect } from 'next/navigation';
import { getServerSession } from 'next-auth';
import { authOptions } from '../lib/auth';

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function Home(props: PageProps) {
  if (props.params) await props.params;
  if (props.searchParams) await props.searchParams;

  try {
    const session = await getServerSession(authOptions);
    // Authenticated users go straight to the dashboard; others see the landing page
    redirect(session ? '/institutional' : '/landing');
  } catch {
    // getServerSession throws in production when NEXTAUTH_SECRET is missing.
    // Fall back to the landing page so the app stays up.
    redirect('/landing');
  }
}
