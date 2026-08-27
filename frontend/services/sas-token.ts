import { API_BASE_URL } from './api';

interface SasTokens {
  imageSasToken: string;
  imageContainerUrl: string;
  expiry: Date;
}

/**
 * Service for managing SAS tokens for direct access to Azure Blob Storage
 * Implements a singleton pattern and handles automatic token refresh
 */
class SasTokenService {
  private tokens: SasTokens | null = null;
  private fetchPromise: Promise<SasTokens> | null = null;

  /**
   * Get valid SAS tokens, refreshing if needed
   * @returns Promise resolving to valid SAS tokens
   */
  async getTokens(): Promise<SasTokens> {
    // If we have tokens and they're not expired (with 5 min buffer)
    if (this.tokens && new Date(this.tokens.expiry).getTime() > Date.now() + 5 * 60 * 1000) {
      return this.tokens;
    }

    // If we're already fetching tokens, return that promise
    if (this.fetchPromise) {
      return this.fetchPromise;
    }

    // Otherwise fetch new tokens
    this.fetchPromise = this.fetchNewTokens();
    try {
      this.tokens = await this.fetchPromise;
      return this.tokens;
    } finally {
      this.fetchPromise = null;
    }
  }

  /**
   * Get a direct URL to an image blob with its SAS token
   * @param blobName Blob name including any folder path
   * @returns Promise resolving to the full URL with SAS token
   */
  async getBlobUrl(blobName: string): Promise<string> {
    try {
      const tokens = await this.getTokens();
      const encodedBlobName = blobName
        .split('/')
        .map((segment) => encodeURIComponent(segment))
        .join('/');
      const blobUrl = `${tokens.imageContainerUrl.replace(/\/$/, '')}/${encodedBlobName}`;
      return tokens.imageSasToken
        ? `${blobUrl}?${tokens.imageSasToken}`
        : blobUrl;
    } catch (error) {
      console.error("Failed to get SAS token for blob:", error);
      throw error;
    }
  }

  /**
   * Private method to fetch new tokens from the API
   */
  private async fetchNewTokens(): Promise<SasTokens> {
    try {
      const response = await fetch(`${API_BASE_URL}/gallery/sas-tokens`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch SAS tokens: ${response.status}`);
      }
      
      const data = await response.json();
      
      return {
        imageSasToken: data.image_sas_token,
        imageContainerUrl: data.image_container_url,
        expiry: new Date(data.expiry)
      };
    } catch (error) {
      console.error("Error fetching SAS tokens:", error);
      throw error;
    }
  }
}

// Export singleton instance
export const sasTokenService = new SasTokenService();
