/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // output: 'export',  // Disabled for API routes - enable for static export
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig
