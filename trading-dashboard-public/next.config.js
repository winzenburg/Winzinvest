/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  compress: true,
  
  // Image optimization enabled (Vercel handles this well)
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    minimumCacheTTL: 31536000,
  },

  // Experimental optimizations for Vercel Pro
  experimental: {
    optimizePackageImports: ['next-auth', 'recharts'],
  },

  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
        ],
      },
    ];
  },

  async redirects() {
    return [
      // Legacy deep-link aliases
      { source: '/strategy', destination: '/methodology#system', permanent: true },
      { source: '/overview',  destination: '/methodology',        permanent: true },
      { source: '/research',  destination: '/methodology#thesis', permanent: true },
      { source: '/analytics', destination: '/dashboard',      permanent: true },
      // Landing page lives at / — redirect old /landing path so bookmarks still work
      { source: '/landing',   destination: '/',                   permanent: true },
      { source: '/institutional', destination: '/dashboard',     permanent: true },
    ];
  },
};

module.exports = nextConfig;
