import { prisma } from '../../lib/prisma';

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function VerifyEmailPage(props: PageProps) {
  const resolved = (props.searchParams ??
    Promise.resolve({})) as Promise<Record<string, string | string[] | undefined>>;
  const params = await resolved;
  const tokenParam = params.token;
  const token =
    typeof tokenParam === 'string' ? tokenParam : Array.isArray(tokenParam) ? tokenParam[0] : '';

  let title = 'Email verification';
  let message =
    'The verification link is invalid or has expired. Please request a new one from the login page.';
  let success = false;

  if (token) {
    try {
      const record = await prisma.verificationToken.findUnique({
        where: { token },
      });

      if (record && record.expires > new Date()) {
        const isVerifyToken = record.identifier.startsWith('verify:');
        const email = record.identifier.replace(/^verify:/, '');

        if (isVerifyToken && email) {
          await prisma.user.updateMany({
            where: { email },
            data: { emailVerified: new Date() },
          });

          await prisma.verificationToken.delete({
            where: { token },
          });

          title = 'Email verified';
          message =
            'Your email has been verified. You can now sign in to your Winzinvest account.';
          success = true;
        }
      }
    } catch (error) {
      console.error('[verify-email] verification failed', error);
    }
  }

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white border border-stone-200 rounded-xl p-8 shadow-sm">
        <h1 className="font-serif text-2xl font-bold text-slate-900 mb-3">
          {title}
        </h1>
        <p className="text-sm text-stone-600 mb-6">{message}</p>
        {success && (
          <a
            href="/login"
            className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold"
          >
            Go to login
          </a>
        )}
      </div>
    </div>
  );
}

