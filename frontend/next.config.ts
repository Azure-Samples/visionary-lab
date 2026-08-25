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
  agentRules: false,
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
      },
      {
        protocol: 'https',
        hostname: '*.azurefd.net',
        pathname: '/**',
      },
      {
        protocol: 'http',
        hostname: '127.0.0.1',
        port: '10000',
        pathname: '/devstoreaccount1/**',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '10000',
        pathname: '/devstoreaccount1/**',
      }
    ],
    // Image optimization settings
    minimumCacheTTL: 86400, // 24 hours
    formats: ['image/webp', 'image/avif'],
    qualities: [75, 85],
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
    optimizePackageImports: ['lucide-react', '@radix-ui/react-icons', 'framer-motion'],
  },
  
  // Enhanced headers with caching and security
  async headers() {
    return [
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
        // Shared security headers. Next.js applies immutable caching to its
        // hashed static assets without making dynamic pages or APIs public.
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
      {
        source: '/api/backend/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'private, no-store, max-age=0',
          },
        ],
      },
    ];
  },
};

export default withBundleAnalyzer(nextConfig);
