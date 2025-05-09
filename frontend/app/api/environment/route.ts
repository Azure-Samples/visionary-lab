import { NextResponse } from 'next/server';

export async function GET() {
  // Build API URL from environment variables
  const protocol = process.env.API_PROTOCOL || 'http';
  const hostname = process.env.API_HOSTNAME || 'localhost';
  const port = process.env.API_PORT || '8000';
  const apiUrl = `${protocol}://${hostname}${port ? `:${port}` : ''}`;

  // Only expose specific environment variables to the frontend
  const envVars = {
    NODE_ENV: process.env.NODE_ENV || 'development',
    API_URL: process.env.NEXT_PUBLIC_API_URL || apiUrl,
    APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION || '0.1.0',
    DEBUG_MODE: process.env.NEXT_PUBLIC_DEBUG_MODE === 'true'
  };

  return NextResponse.json(envVars);
} 