/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverComponentsExternalPackages: [],
  },
  images: {
    remotePatterns: [],
  },
  // Evita CORS: browser → :3000/api/v1/* → FastAPI :8000
  async rewrites() {
    const api = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${api}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
