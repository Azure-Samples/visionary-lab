import type { NextConfig } from "next";

// Read environment variables with fallbacks
const API_HOSTNAME = process.env.API_HOSTNAME || 'localhost';
const API_PORT = process.env.API_PORT || '8000';
const API_PROTOCOL = process.env.API_PROTOCOL || 'http';
const STORAGE_ACCOUNT_NAME = process.env.STORAGE_ACCOUNT_NAME || '<storage-account-name>';

const nextConfig: NextConfig = {
  /* config options here */
  output: 'standalone',
  images: {
    remotePatterns: [
      {
        protocol: API_PROTOCOL as 'http' | 'https',
        hostname: API_HOSTNAME,
        port: API_PORT,
        pathname: '/api/v1/gallery/asset/**',
      },
      {
        protocol: 'https',
        hostname: `${STORAGE_ACCOUNT_NAME}.blob.core.windows.net`,
        port: '',
        pathname: '/**',
      },
    ],
  },
  // Make environment variables available to the browser
  env: {
    API_HOSTNAME,
    API_PORT,
    API_PROTOCOL,
    STORAGE_ACCOUNT_NAME,
  },
};

export default nextConfig;