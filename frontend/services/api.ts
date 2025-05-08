/**
 * API service for interacting with the backend API
 */

// Build API base URL from environment variables
// These variables are set in next.config.ts and available at runtime
const getApiBaseUrl = () => {
  const protocol = process.env.API_PROTOCOL || 'http';
  const hostname = process.env.API_HOSTNAME || 'localhost';
  const port = process.env.API_PORT || '8000';
  
  // Only include port in the URL if it's non-standard
  // Standard ports: 80 for HTTP, 443 for HTTPS
  let includePort = true;
  if ((protocol === 'http' && port === '80') || (protocol === 'https' && port === '443')) {
    includePort = false;
  }
  
  // Build the API base URL
  const baseUrl = `${protocol}://${hostname}${includePort && port ? `:${port}` : ''}/api/v1`;
  
  // Log the constructed URL for debugging
  console.log('API Base URL:', baseUrl);
  console.log('Environment variables:', { 
    API_PROTOCOL: process.env.API_PROTOCOL,
    API_HOSTNAME: process.env.API_HOSTNAME,
    API_PORT: process.env.API_PORT,
    includePort: includePort
  });
  
  return baseUrl;
};

export const API_BASE_URL = getApiBaseUrl();

// Enable debug mode to log API requests
const DEBUG = true;

// Gallery types
export enum MediaType {
  IMAGE = "image",
  VIDEO = "video",
}

export interface GalleryItem {
  id: string;
  name: string;
  media_type: MediaType;
  url: string;
  container: string;
  size: number;
  content_type: string;
  creation_time: string;
  last_modified: string;
  metadata?: Record<string, string>;
}

export interface GalleryResponse {
  success: boolean;
  message: string;
  total: number;
  limit: number;
  offset: number;
  items: GalleryItem[];
  continuation_token?: string;
}

export interface GalleryUploadResponse {
  success: boolean;
  message: string;
  file_id: string;
  blob_name: string;
  container: string;
  url: string;
  size: number;
  content_type: string;
  original_filename: string;
  metadata?: Record<string, string>;
}

/**
 * Upload a video to the gallery
 */
export async function uploadVideoToGallery(
  videoBlob: Blob, 
  fileName: string, 
  metadata: Record<string, any>
): Promise<GalleryUploadResponse> {
  const url = `${API_BASE_URL}/gallery/upload`;
  
  if (DEBUG) {
    console.log(`Uploading video to gallery: ${fileName}`);
    console.log(`POST ${url}`);
    console.log('Metadata:', metadata);
  }

  // Create form data for the upload
  const formData = new FormData();
  formData.append('file', videoBlob, fileName);
  formData.append('media_type', 'video');
  
  // Add metadata as JSON string
  if (metadata) {
    formData.append('metadata', JSON.stringify(metadata));
  }
  
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (DEBUG) {
    console.log(`Response status: ${response.status} ${response.statusText}`);
    if (!response.ok) {
      console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
    }
  }

  if (!response.ok) {
    throw new Error(`Failed to upload video to gallery: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  
  if (DEBUG) {
    console.log('Response data:', data);
  }
  
  return data;
}

/**
 * Fetch videos from the gallery
 */
export async function fetchGalleryVideos(
  limit: number = 50, 
  offset: number = 0,
  continuationToken?: string,
  prefix?: string
): Promise<GalleryResponse> {
  // Build query parameters
  const params = new URLSearchParams();
  params.append('limit', String(limit));
  params.append('offset', String(offset));
  if (continuationToken) {
    params.append('continuation_token', continuationToken);
  }
  if (prefix) {
    params.append('prefix', prefix);
  }

  const url = `${API_BASE_URL}/gallery/videos?${params.toString()}`;
  
  if (DEBUG) {
    console.log(`Fetching gallery videos`);
    console.log(`GET ${url}`);
  }
  
  try {
    const response = await fetch(url);

    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch gallery videos: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (DEBUG) {
      console.log('Response data:', data);
    }
    
    return data;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error(`Network error when fetching gallery videos: ${errorMessage}`);
    throw error;
  }
}

/**
 * Fetch images from the gallery
 */
export async function fetchGalleryImages(
  limit: number = 50, 
  offset: number = 0,
  continuationToken?: string,
  prefix?: string
): Promise<GalleryResponse> {
  // Build query parameters
  const params = new URLSearchParams();
  params.append('limit', String(limit));
  params.append('offset', String(offset));
  if (continuationToken) {
    params.append('continuation_token', continuationToken);
  }
  if (prefix) {
    params.append('prefix', prefix);
  }

  const url = `${API_BASE_URL}/gallery/images?${params.toString()}`;
  
  if (DEBUG) {
    console.log(`Fetching gallery images`);
    console.log(`GET ${url}`);
  }
  
  try {
    const response = await fetch(url);

    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch gallery images: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (DEBUG) {
      console.log('Response data:', data);
    }
    
    return data;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error(`Network error when fetching gallery images: ${errorMessage}`);
    throw error;
  }
}

/**
 * Delete an asset from the gallery
 */
export async function deleteGalleryAsset(
  blobName: string, 
  mediaType: MediaType
): Promise<{success: boolean, message: string}> {
  const params = new URLSearchParams();
  params.append('blob_name', blobName);
  params.append('media_type', mediaType);

  const url = `${API_BASE_URL}/gallery/delete?${params.toString()}`;
  
  if (DEBUG) {
    console.log(`Deleting gallery asset: ${blobName}`);
    console.log(`DELETE ${url}`);
  }
  
  try {
    const response = await fetch(url, {
      method: 'DELETE'
    });

    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to delete gallery asset: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (DEBUG) {
      console.log('Response data:', data);
    }
    
    return data;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error(`Network error when deleting gallery asset: ${errorMessage}`);
    throw error;
  }
}

/**
 * Interface for video analysis response
 */
export interface VideoAnalysisResponse {
  summary: string;
  products: string;
  tags: string[];
  feedback: string;
}

/**
 * Analyze a video using AI
 */
export async function analyzeVideo(videoPath: string, retries = 3): Promise<VideoAnalysisResponse> {
  const url = `${API_BASE_URL}/videos/analyze`;
  
  if (DEBUG) {
    console.log(`Analyzing video at path: ${videoPath}`);
    console.log(`POST ${url}`);
  }
  
  let attempt = 0;
  let lastError: Error | null = null;
  
  while (attempt < retries) {
    try {
      attempt++;
      
      if (attempt > 1) {
        console.log(`Retry attempt ${attempt}/${retries} for video analysis`);
      }
      
      // Add a timeout to prevent hanging requests
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ video_path: videoPath }),
        signal: controller.signal
      });
      
      // Clear the timeout
      clearTimeout(timeoutId);
      
      if (DEBUG) {
        console.log(`Response status: ${response.status} ${response.statusText}`);
        if (!response.ok) {
          console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
        }
      }
      
      if (!response.ok) {
        throw new Error(`Failed to analyze video: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (DEBUG) {
        console.log('Analysis response data:', data);
      }
      
      return data;
    } catch (error) {
      console.error(`Video analysis attempt ${attempt}/${retries} failed:`, error);
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // If it's the last attempt, throw the error
      if (attempt >= retries) {
        throw lastError;
      }
      
      // Wait before retrying - increasing delay between retries
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
  
  // This should never happen due to the throw in the loop, but TypeScript requires a return
  throw lastError || new Error("Video analysis failed after retries");
}

/**
 * Interface for image analysis response
 */
export interface ImageAnalysisResponse {
  description: string;
  products: string;
  tags: string[];
  feedback: string;
}

/**
 * Analyze an image using AI
 */
export async function analyzeImage(imageUrl: string, retries = 3): Promise<ImageAnalysisResponse> {
  const url = `${API_BASE_URL}/images/analyze`;
  
  if (DEBUG) {
    console.log(`Analyzing image at URL: ${imageUrl}`);
    console.log(`POST ${url}`);
  }
  
  let attempt = 0;
  let lastError: Error | null = null;
  
  while (attempt < retries) {
    try {
      attempt++;
      
      if (attempt > 1) {
        console.log(`Retry attempt ${attempt}/${retries} for image analysis`);
      }
      
      // Add a timeout to prevent hanging requests
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ image_path: imageUrl }),
        signal: controller.signal
      });
      
      // Clear the timeout
      clearTimeout(timeoutId);
      
      if (DEBUG) {
        console.log(`Response status: ${response.status} ${response.statusText}`);
        if (!response.ok) {
          console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
        }
      }
      
      if (!response.ok) {
        throw new Error(`Failed to analyze image: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (DEBUG) {
        console.log('Analysis response data:', data);
      }
      
      return data;
    } catch (error) {
      console.error(`Image analysis attempt ${attempt}/${retries} failed:`, error);
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // If it's the last attempt, throw the error
      if (attempt >= retries) {
        throw lastError;
      }
      
      // Wait before retrying - increasing delay between retries
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
  
  // This should never happen due to the throw in the loop, but TypeScript requires a return
  throw lastError || new Error("Image analysis failed after retries");
}

/**
 * Update metadata for an asset in the gallery
 */
export async function updateAssetMetadata(
  blobName: string,
  mediaType: MediaType,
  metadata: Record<string, any>
): Promise<any> {
  const params = new URLSearchParams();
  params.append('blob_name', blobName);
  params.append('media_type', mediaType);
  
  const url = `${API_BASE_URL}/gallery/metadata?${params.toString()}`;
  
  if (DEBUG) {
    console.log(`Updating metadata for asset: ${blobName}`);
    console.log(`PUT ${url}`);
    console.log('Metadata:', metadata);
  }
  
  try {
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ metadata }),
    });
    
    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }
    
    if (!response.ok) {
      throw new Error(`Failed to update metadata: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (DEBUG) {
      console.log('Response data:', data);
    }
    
    return data;
  } catch (error) {
    console.error('Error updating metadata:', error);
    throw error;
  }
}

/**
 * Fetch all folders from the gallery
 */
export async function fetchFolders(
  mediaType?: MediaType
): Promise<{folders: string[], folder_hierarchy: any}> {
  let url = `${API_BASE_URL}/gallery/folders`;
  
  if (mediaType) {
    url += `?media_type=${mediaType}`;
  }
  
  // Always log for debugging this issue
  console.log(`Fetching folders from: ${url}`);
  console.log('Current API_BASE_URL:', API_BASE_URL);
  
  try {
    // Add a timeout to prevent hanging requests
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      signal: controller.signal
    });
    
    // Clear the timeout
    clearTimeout(timeoutId);
    
    console.log(`Response status: ${response.status} ${response.statusText}`);
    
    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Could not read response text');
      console.error('Error response:', errorText);
      throw new Error(`Failed to fetch folders: ${response.status} ${response.statusText} - ${errorText}`);
    }
    
    const data = await response.json();
    console.log('Folders response data:', data);
    
    return {
      folders: data.folders || [],
      folder_hierarchy: data.folder_hierarchy || {}
    };
  } catch (error) {
    // Enhanced error logging
    console.error('Error fetching folders:', error);
    console.error('Error details:', {
      message: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : 'No stack trace available',
      url: url
    });
    
    // Return empty data instead of throwing to prevent UI errors
    return {
      folders: [],
      folder_hierarchy: {}
    };
  }
}

/**
 * Create a new folder in the gallery
 */
export async function createFolder(
  folderPath: string,
  mediaType: MediaType = MediaType.IMAGE
): Promise<{success: boolean, folder_path: string}> {
  const url = `${API_BASE_URL}/gallery/folders`;
  
  if (DEBUG) {
    console.log(`Creating folder: ${folderPath}`);
    console.log(`POST ${url}`);
  }
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        folder_path: folderPath,
        media_type: mediaType
      }),
    });
    
    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }
    
    if (!response.ok) {
      throw new Error(`Failed to create folder: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (DEBUG) {
      console.log('Create folder response data:', data);
    }
    
    return {
      success: data.success,
      folder_path: data.folder_path
    };
  } catch (error) {
    console.error('Error creating folder:', error);
    throw error;
  }
}

/**
 * Move an asset to a different folder
 */
export async function moveAsset(
  blobName: string,
  targetFolder: string,
  mediaType: MediaType
): Promise<{success: boolean, message: string}> {
  const url = `${API_BASE_URL}/gallery/move`;
  
  if (DEBUG) {
    console.log(`Moving asset ${blobName} to folder ${targetFolder}`);
    console.log(`PUT ${url}`);
  }
  
  try {
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        blob_name: blobName,
        media_type: mediaType,
        target_folder: targetFolder
      }),
    });
    
    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }
    
    if (!response.ok) {
      throw new Error(`Failed to move asset: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (DEBUG) {
      console.log('Move asset response data:', data);
    }
    
    return {
      success: data.success,
      message: data.message
    };
  } catch (error) {
    console.error('Error moving asset:', error);
    throw error;
  }
}

/**
 * Edit an image using gpt-image-1
 */
export async function editImage(
  sourceImages: File | File[],
  prompt: string, 
  n: number = 1,
  size: string = "auto",
  quality: string = "auto"
): Promise<any> {
  const url = `${API_BASE_URL}/images/edit/upload`;
  
  if (DEBUG) {
    const imageCount = Array.isArray(sourceImages) ? sourceImages.length : 1;
    console.log(`Editing ${imageCount} image(s) with prompt: ${prompt}`);
    console.log(`POST ${url}`);
  }
  
  // Create a FormData object to send the file and parameters
  const formData = new FormData();
  
  // Handle single image or multiple images
  if (Array.isArray(sourceImages)) {
    sourceImages.forEach((img) => {
      formData.append('image', img);
    });
  } else {
    formData.append('image', sourceImages);
  }
  
  formData.append('prompt', prompt);
  formData.append('n', n.toString());
  formData.append('size', size);
  formData.append('model', 'gpt-image-1');
  formData.append('quality', quality);
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to edit image: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (DEBUG) {
      console.log('Edited image response data:', data);
    }
    
    return data;
  } catch (error) {
    console.error('Error editing image:', error);
    throw error;
  }
}

/**
 * Analyze an image using AI directly from base64 data
 */
export async function analyzeImageFromBase64(base64Image: string, retries = 3): Promise<ImageAnalysisResponse> {
  const url = `${API_BASE_URL}/images/analyze`;
  
  // Make sure the base64 string doesn't include the data URL prefix
  const cleanBase64 = base64Image.replace(/^data:image\/[a-z]+;base64,/, "");
  
  if (DEBUG) {
    console.log("Analyzing image from base64 data");
    console.log(`POST ${url}`);
  }
  
  let attempt = 0;
  let lastError: Error | null = null;
  
  while (attempt < retries) {
    try {
      attempt++;
      
      if (attempt > 1) {
        console.log(`Retry attempt ${attempt}/${retries} for image analysis`);
      }
      
      // Add a timeout to prevent hanging requests
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ base64_image: cleanBase64 }),
        signal: controller.signal
      });
      
      // Clear the timeout
      clearTimeout(timeoutId);
      
      if (DEBUG) {
        console.log(`Response status: ${response.status} ${response.statusText}`);
        if (!response.ok) {
          console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
        }
      }
      
      if (!response.ok) {
        throw new Error(`Failed to analyze image: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (DEBUG) {
        console.log('Analysis response data:', data);
      }
      
      return data;
    } catch (error) {
      console.error(`Image analysis attempt ${attempt}/${retries} failed:`, error);
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // If it's the last attempt, throw the error
      if (attempt >= retries) {
        throw lastError;
      }
      
      // Wait before retrying - increasing delay between retries
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
  
  // This should never happen due to the throw in the loop, but TypeScript requires a return
  throw lastError || new Error("Image analysis failed after retries");
}

export interface EnhancePromptRequest {
  original_prompt: string;
}

export interface EnhancePromptResponse {
  enhanced_prompt: string;
}

/**
 * Enhance an image prompt using the backend API
 */
export async function enhanceImagePrompt(prompt: string): Promise<string> {
  const url = `${API_BASE_URL}/images/prompt/enhance`;
  
  if (DEBUG) {
    console.log(`Enhancing image prompt: ${prompt}`);
    console.log(`POST ${url}`);
  }
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ original_prompt: prompt }),
    });

    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to enhance image prompt: ${response.status} ${response.statusText}`);
    }

    const data: EnhancePromptResponse = await response.json();
    
    if (DEBUG) {
      console.log('Enhanced image prompt:', data.enhanced_prompt);
    }
    
    return data.enhanced_prompt;
  } catch (error) {
    console.error('Error enhancing image prompt:', error);
    throw error;
  }
}

/**
 * Generate images using GPT-Image-1
 */
export async function generateImages(
  prompt: string, 
  n: number = 1,
  size: string = "1024x1024",
  response_format: string = "b64_json",
  background: string = "auto",
  outputFormat: string = "png",
  quality: string = "auto"
): Promise<any> {
  const url = `${API_BASE_URL}/images/generate`;
  
  if (DEBUG) {
    console.log(`Generating images with prompt: ${prompt}`);
    console.log(`POST ${url}`);
  }
  
  const payload = {
    prompt,
    n,
    size,
    response_format,
    background,
    output_format: outputFormat,
    quality
  };
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to generate images: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (DEBUG) {
      console.log('Generated images response data:', data);
    }
    
    return data;
  } catch (error) {
    console.error('Error generating images:', error);
    throw error;
  }
}

/**
 * Save generated images to blob storage
 */
export async function saveGeneratedImages(
  generationResponse: any,
  prompt: string,
  saveAll: boolean = true,
  folderPath: string = "",
  outputFormat: string = "png",
  model: string = "gpt-image-1",
  background: string = "auto",
  size: string = "1024x1024"
): Promise<any> {
  const url = `${API_BASE_URL}/images/save`;
  
  if (DEBUG) {
    console.log(`Saving generated images to blob storage`);
    console.log(`POST ${url}`);
  }
  
  const payload = {
    generation_response: generationResponse,
    prompt,
    save_all: saveAll,
    folder_path: folderPath,
    output_format: outputFormat,
    model,
    background,
    size
  };
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to save images: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (DEBUG) {
      console.log('Saved images response data:', data);
    }
    
    return data;
  } catch (error) {
    console.error('Error saving images:', error);
    throw error;
  }
}