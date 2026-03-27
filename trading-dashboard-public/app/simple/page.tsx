import { redirect } from 'next/navigation';

/** Legacy URL — consolidated into the trading dashboard. */
export default function SimpleRedirectPage() {
  redirect('/dashboard');
}
