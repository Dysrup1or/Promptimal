import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // basePath: '/promptly-landing', // Uncomment for GitHub Pages subdirectory deployment
};

export default nextConfig;
