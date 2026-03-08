/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // output: 'export',  // Disabled - API routes require Node.js runtime
  // For static export: comment out API routes and use mock data
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig
