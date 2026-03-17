import { redirect } from 'next/navigation';

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function Home(props: PageProps) {
  if (props.params) await props.params;
  if (props.searchParams) await props.searchParams;
  redirect('/landing');
}
