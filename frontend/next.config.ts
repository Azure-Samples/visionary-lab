import type { NextConfig } from "next";

// Bundle analyzer
// eslint-disable-next-line @typescript-eslint/no-require-imports
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

// const STORAGE_ACCOUNT_NAME = process.env.NEXT_PUBLIC_STORAGE_ACCOUNT_NAME;

const nextConfig: NextConfig = {
  /* config options here */
  output: 'standalone',
  // Add allowedDevOrigins to prevent the CORS warning in development
  allowedDevOrigins: ['localhost', '127.0.0.1', '::1'],
  
  // Enable compression
  compress: true,
  
  // Optimize static generation
  trailingSlash: false,
  
  // Image optimization configuration for Azure Blob Storage
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.blob.core.windows.net',
        pathname: '/**',
      }
    ],
    // Image optimization settings
    minimumCacheTTL: 86400, // 24 hours
    formats: ['image/webp', 'image/avif'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    // Enable unoptimized images for external URLs with query params (SAS tokens)
    unoptimized: false,
  },
  
  experimental: {
    serverActions: {
      bodySizeLimit: '26mb', // Increased for large image uploads
    },
    // Enable modern bundling optimizations
    optimizePackageImports: ['lucide-react', '@radix-ui/react-icons'],
    // Enable turbo mode for faster builds
    turbo: {
      rules: {
        '*.svg': {
          loaders: ['@svgr/webpack'],
          as: '*.js',
        },
      },
    },
  },
  
  
  // Disable ESLint during builds
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Disable TypeScript checks during builds
  typescript: {
    ignoreBuildErrors: true,
  },
  
  // Enhanced headers with caching and security
  async headers() {
    return [
      {
        // Add CORS headers to all API routes
        source: "/api/:path*",
        headers: [
          { key: "Access-Control-Allow-Credentials", value: "true" },
          { key: "Access-Control-Allow-Origin", value: "*" },
          { key: "Access-Control-Allow-Methods", value: "GET,POST,PUT,DELETE,OPTIONS" },
          { key: "Access-Control-Allow-Headers", value: "X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, Authorization" },
        ]
      },
      {
        // Service worker caching
        source: '/sw.js',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=0, must-revalidate',
          },
          {
            key: 'Service-Worker-Allowed',
            value: '/',
          },
        ],
      },
      {
        // Cache static assets
        source: '/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },

      {
        // Security headers
        source: '/(.*)',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
        ],
      },
    ];
  },
};

export default withBundleAnalyzer(nextConfig);
