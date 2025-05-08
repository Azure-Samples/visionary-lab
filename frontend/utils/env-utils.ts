// Environment variable utilities

interface EnvVariables {
  NODE_ENV: string;
  API_URL: string;
  APP_VERSION: string;
  DEBUG_MODE: boolean;
}

interface ApiStatus {
  services: {
    image_generation: boolean;
    llm: boolean;
    storage: boolean;
  };
  providers: {
    using_azure_openai: boolean;
    using_direct_openai: boolean;
  };
  summary: {
    all_services_ready: boolean;
    image_generation_client: string;
    llm_client: string;
    storage: string;
  };
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
    return {
      NODE_ENV: process.env.NODE_ENV || 'development',
      API_URL: '',
      APP_VERSION: '0.0.0',
      DEBUG_MODE: false
    };
  }
}

// Build API URL from environment variables
const getApiUrl = (endpoint: string): string => {
  const protocol = process.env.API_PROTOCOL || 'http';
  const hostname = process.env.API_HOSTNAME || 'localhost';
  const port = process.env.API_PORT || '8000';
  return `${protocol}://${hostname}${port ? `:${port}` : ''}/api/v1/${endpoint}`;
};

export async function getApiStatus(): Promise<ApiStatus | null> {
  try {
    const apiUrl = getApiUrl('env/status');
    const response = await fetch(apiUrl);
    if (!response.ok) {
      throw new Error(`Failed to fetch API status from ${apiUrl}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching API status:', error);
    return null;
  }
} 