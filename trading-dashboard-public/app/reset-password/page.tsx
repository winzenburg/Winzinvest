import { prisma } from '../../lib/prisma';
import ResetPasswordClient from './reset-password-client';

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function ResetPasswordPage(props: PageProps) {
  const resolved = (props.searchParams ??
    Promise.resolve({})) as Promise<Record<string, string | string[] | undefined>>;
  const params = await resolved;
  const tokenParam = params.token;
  const token =
    typeof tokenParam === 'string'
      ? tokenParam
      : Array.isArray(tokenParam)
        ? tokenParam[0]
        : '';

  if (!token) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-white border border-stone-200 rounded-xl p-6 shadow-sm">
          <h1 className="font-serif text-2xl font-bold text-slate-900 mb-3">
            Invalid link
          </h1>
          <p className="text-sm text-stone-600 mb-4">
            This password reset link is missing or invalid. Please request a new
            one from the forgot password page.
          </p>
          <a
            href="/forgot-password"
            className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold"
          >
            Request new link
          </a>
        </div>
      </div>
    );
  }

  const record = await prisma.verificationToken.findUnique({
    where: { token },
    select: { expires: true, identifier: true },
  });

  if (!record || record.expires < new Date() || !record.identifier.startsWith('reset:')) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-white border border-stone-200 rounded-xl p-6 shadow-sm">
          <h1 className="font-serif text-2xl font-bold text-slate-900 mb-3">
            Link expired
          </h1>
          <p className="text-sm text-stone-600 mb-4">
            This password reset link has expired or is no longer valid. Please
            request a new one.
          </p>
          <a
            href="/forgot-password"
            className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold"
          >
            Request new link
          </a>
        </div>
      </div>
    );
  }

  return <ResetPasswordClient token={token} />;
}

