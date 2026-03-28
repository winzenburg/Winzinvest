import type { Metadata } from 'next';
import { Inter, Playfair_Display, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import Providers from './Providers';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const playfair = Playfair_Display({
  subsets: ['latin'],
  variable: '--font-playfair',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  metadataBase: new URL('https://winzinvest.com'),
  title: {
    default: 'Winzinvest – Systematic portfolio automation for disciplined traders',
    template: 'Winzinvest – %s',
  },
  description:
    'Winzinvest is systematic execution software for swing traders. Automate equity momentum, options premium, and risk management through Interactive Brokers with institutional-style safeguards.',
  keywords: [
    'Winzinvest',
    'automated trading',
    'systematic trading',
    'swing trading automation',
    'options income',
    'covered calls',
    'cash-secured puts',
    'Interactive Brokers',
    'portfolio risk management',
  ],
  openGraph: {
    type: 'website',
    url: 'https://winzinvest.com/',
    siteName: 'Winzinvest',
    title: 'Winzinvest – Systematic portfolio automation for disciplined traders',
    description:
      'Automated equity momentum and options premium strategies with 13 execution checks on every order and institutional-grade risk gates.',
    images: [
      {
        url: '/illustrations/hero-l-amber-path.png',
        width: 1200,
        height: 630,
        alt: 'A figure walking a calm amber path between fields — representing steady progress with systematic discipline.',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@winzinvest', // safe even if handle is not yet active
    title: 'Winzinvest – Systematic portfolio automation for disciplined traders',
    description:
      'Automated equity momentum and options premium strategies with institutional-style risk management and execution gates.',
    images: ['/illustrations/hero-l-amber-path.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const organizationJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Winzinvest',
    url: 'https://winzinvest.com/',
    description:
      'Winzinvest is systematic execution software for swing traders, automating equity momentum, options premium, and portfolio risk management through Interactive Brokers.',
    logo: 'https://winzinvest.com/illustrations/hero-l-amber-path.png',
    sameAs: [
      'https://github.com/winzenburg/MissionControl',
    ],
  };

  return (
    <html
      lang="en"
      className={`${inter.variable} ${playfair.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
        <script
          type="application/ld+json"
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
      </body>
    </html>
  );
}
