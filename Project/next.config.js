/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    domains: ["localhost"],
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**.r2.cloudflarestorage.com",
      },
      {
        protocol: "https",
        hostname: "**.cloudflare.com",
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/py/:path*",
        destination: process.env.PYTHON_BACKEND_URL
          ? `${process.env.PYTHON_BACKEND_URL}/api/:path*`
          : "http://localhost:8000/api/:path*",
      },
    ];
  },
  // Enable experimental features if needed
  experimental: {
    serverActions: true,
  },
};

module.exports = nextConfig;
