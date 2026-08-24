import { NextResponse } from 'next/server';

export async function GET() {
  // Check if running in GitHub Codespaces
  const isCodespaces = typeof process.env.CODESPACE_NAME === 'string' && 
                       process.env.CODESPACE_NAME.length > 0;
                       
  // Only expose specific environment variables to the frontend
  const envVars = {
    NODE_ENV: process.env.NODE_ENV || 'development',
    API_URL: '/api/backend/api/v1',
    APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION || '0.1.0',
    DEBUG_MODE: process.env.NEXT_PUBLIC_DEBUG_MODE === 'true',
    IS_CODESPACES: isCodespaces
  };

  return NextResponse.json(envVars);
}
