import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Explicit route handlers (app/api/) take priority; rewrites cover the rest
     (e.g. /api/library/status, /api/library/index, /api/transcribe). */
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://localhost:8000/api/:path*" },
    ];
  },
};

export default nextConfig;
