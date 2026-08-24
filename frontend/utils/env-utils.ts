// Environment variable utilities

import { API_BASE_URL } from '@/services/api';

interface EnvVariables {
  NODE_ENV: string;
  API_URL: string;
  APP_VERSION: string;
  DEBUG_MODE: boolean;
  IS_CODESPACES: boolean;
}

interface ApiStatus {
  set: string[];
  missing: string[];
}

export async function getEnvironmentVariables(): Promise<EnvVariables> {
  try {
    const response = await fetch('/api/environment');
    if (!response.ok) {
      throw new Error('Failed to fetch environment variables');
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching environment variables:', error);
    // Check if running in GitHub Codespaces
    const isCodespaces = typeof process.env.CODESPACE_NAME === 'string' && 
                         process.env.CODESPACE_NAME.length > 0;
                         
    return {
      NODE_ENV: process.env.NODE_ENV || 'development',
      API_URL: '',
      APP_VERSION: '0.0.0',
      DEBUG_MODE: false,
      IS_CODESPACES: isCodespaces
    };
  }
}

export async function getApiStatus(): Promise<ApiStatus | null> {
  try {
    const url = `${API_BASE_URL}/env/status`;
    
    console.log(`Checking API status at: ${url}`);
    
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to fetch API status');
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching API status:', error);
    return null;
  }
}
