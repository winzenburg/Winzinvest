'use client';

import { useEffect } from 'react';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error('[GlobalError]', error);
  }, [error]);

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-8">
      <div className="max-w-md w-full">
        <div className="border border-red-800 bg-red-950/40 rounded-lg p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-red-400 text-2xl">⚠</span>
            <h2 className="text-red-300 text-lg font-semibold">Something went wrong</h2>
          </div>
          <p className="text-gray-400 text-sm">
            An unexpected error occurred while rendering this page. The error has been
            logged. Try refreshing — if it persists, the backend data files may be
            temporarily unavailable.
          </p>
          {error.digest && (
            <p className="text-gray-600 text-xs font-mono">Digest: {error.digest}</p>
          )}
          <button
            onClick={reset}
            className="w-full py-2 px-4 bg-red-900 hover:bg-red-800 text-red-100 text-sm
                       rounded transition-colors border border-red-700"
          >
            Try again
          </button>
        </div>
      </div>
    </div>
  );
}
