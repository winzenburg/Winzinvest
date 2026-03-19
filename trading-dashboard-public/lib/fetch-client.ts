/**
 * Client-side authenticated fetch helper.
 *
 * Wraps the native fetch() and automatically handles HTTP 401 responses by
 * redirecting the user to the login page so sessions that expire mid-visit
 * don't silently produce empty data.
 *
 * Usage (in a React component):
 *   import { fetchWithAuth } from '@/lib/fetch-client';
 *   const data = await fetchWithAuth('/api/dashboard');
 */

export class AuthError extends Error {
  status = 401;
}

/**
 * Thin wrapper around fetch that throws `AuthError` on a 401 and optionally
 * redirects the user to the login page. All other network / HTTP errors are
 * re-thrown as regular `Error` instances.
 */
export async function fetchWithAuth(
  input: RequestInfo | URL,
  init?: RequestInit,
  opts: { redirectOnUnauth?: boolean } = { redirectOnUnauth: true },
): Promise<Response> {
  const res = await fetch(input, init);

  if (res.status === 401) {
    if (opts.redirectOnUnauth && typeof window !== 'undefined') {
      const returnUrl = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login?callbackUrl=${returnUrl}`;
    }
    throw new AuthError('Session expired — please log in again.');
  }

  return res;
}

/**
 * Convenience wrapper: fetches JSON and returns the parsed value.
 * Returns `null` on auth failure (after redirect) or any other error.
 */
export async function fetchJsonWithAuth<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T | null> {
  try {
    const res = await fetchWithAuth(input, init);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof AuthError) return null;
    console.error('[fetchJsonWithAuth] error:', err);
    return null;
  }
}
