import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Note: Removed 'output: export' to enable API routes for SSE streaming
  // For static deployment, use a separate static build without API routes
  images: {
    unoptimized: true,
  },
  // Configure environment variables
  env: {
    PROMPTLY_API_URL: process.env.PROMPTLY_API_URL || 'http://localhost:8000',
  },
  // basePath: '/promptly-landing', // Uncomment for GitHub Pages subdirectory deployment
};

export default nextConfig;
