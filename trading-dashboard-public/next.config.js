/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // output: 'export',  // Disabled - API routes require Node.js runtime
  images: {
    unoptimized: true,
  },
  // Edge runtime for Cloudflare Pages is set per-route via:
  //   export const runtime = 'edge';
  // The global experimental.runtime config was removed in Next.js 14 and is
  // silently ignored in Next.js 15. No global override needed here.
};

module.exports = nextConfig;
