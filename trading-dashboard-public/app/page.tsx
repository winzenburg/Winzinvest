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

  // getServerSession throws if NEXTAUTH_SECRET is missing — catch only that,
  // not the NEXT_REDIRECT thrown by redirect() itself.
  let session = null;
  try {
    session = await getServerSession(authOptions);
  } catch {
    // Missing NEXTAUTH_SECRET in production — fall through to landing page
  }

  // redirect() must be called outside try/catch (it throws NEXT_REDIRECT internally)
  redirect(session ? '/institutional' : '/landing');
}
