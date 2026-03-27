/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
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
