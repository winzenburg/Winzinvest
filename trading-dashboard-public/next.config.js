/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // output: 'export',  // Disabled - API routes require Node.js runtime
  images: {
    unoptimized: true,
  },
  // Required for @opennextjs/cloudflare — tells Next.js to use the Edge-compatible
  // build path. Does not affect `npm run dev` or `npm run build` locally.
  ...(process.env.BUILD_TARGET === 'cloudflare' && {
    experimental: {
      runtime: 'edge',
    },
  }),
};

module.exports = nextConfig;
