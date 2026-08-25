/**
 * API service for interacting with the backend API
 */

// Browser traffic always uses the same-origin Next.js proxy. Server-side callers
// can still use the internal backend URL directly.
const API_PROTOCOL = process.env.NEXT_PUBLIC_API_PROTOCOL || 'http';
const API_HOSTNAME = process.env.NEXT_PUBLIC_API_HOSTNAME || 'localhost';
const API_PORT = process.env.NEXT_PUBLIC_API_PORT || '8000';
const configuredDirectUrl =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  (API_PORT
    ? `${API_PROTOCOL}://${API_HOSTNAME}:${API_PORT}`
    : `${API_PROTOCOL}://${API_HOSTNAME}`);
const normalizedDirectUrl = configuredDirectUrl.replace(/\/$/, '');
export const DIRECT_API_BASE_URL = normalizedDirectUrl.endsWith('/api/v1')
  ? normalizedDirectUrl
  : `${normalizedDirectUrl}/api/v1`;
export const API_BASE_URL =
  typeof window === 'undefined' ? DIRECT_API_BASE_URL : '/api/backend/api/v1';

// Enable debug mode to log API requests
const API_DEBUG = process.env.NEXT_PUBLIC_DEBUG_MODE === 'true';

if (API_DEBUG) {
  console.log(`API configured with: ${API_BASE_URL}`);
}

// Types for API requests and responses
// Gallery types
export interface GalleryItem {
  id: string;
  name: string;
  media_type: "image";
  url: string;
  container: string;
  size: number;
  content_type: string;
  creation_time: string;
  last_modified: string;
  metadata?: AssetMetadata;
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

/**
 * Interface for image metadata
 */
export interface AssetMetadata {
  [key: string]: string | number | boolean | string[] | object | undefined;
  prompt?: string;
  description?: string;
  tags?: string[];
  width?: string;
  height?: string;
  has_transparency?: string;
  analysis?: {
    summary?: string;
    products?: string;
    tags?: string[];
    feedback?: string;
    analyzed_at?: string;
    analyzed?: boolean;
  };
  has_analysis?: boolean;
}

/**
 * Interface for image generation response
 */
export interface InputTokensDetails {
  text_tokens?: number;
  image_tokens?: number;
}

export interface TokenUsage {
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  input_tokens_details?: InputTokensDetails;
}

export interface ImageGenerationResponse {
  success: boolean;
  message?: string;
  error?: string;
  imgen_model_response?: {
    created?: number;
    data?: Array<{
      url?: string;
      b64_json?: string;
      revised_prompt?: string;
      [key: string]: unknown;
    }>;
    [key: string]: unknown;
  };
  token_usage?: TokenUsage;
  [key: string]: unknown;
}

/**
 * Interface for image save response
 */
export interface ImageSaveResponse {
  success: boolean;
  message: string;
  saved_images: Array<{
    blob_name: string;
    url: string;
    original_index: number;
  }>;
  total_saved: number;
  prompt?: string;
  analysis_results?: Array<{
    blob_name: string;
    asset_id?: string;
    analysis?: {
      description?: string;
      products?: string;
      tags?: string[];
      feedback?: string;
    };
    success: boolean;
    error?: string;
  }>;
  analyzed: boolean;
}

export type PipelineStep = 'generate' | 'edit' | 'save' | 'analyze';

export interface PipelineStepResult {
  step: PipelineStep;
  success: boolean;
  message?: string;
  details?: Record<string, unknown>;
}

export interface PipelineSaveOptions {
  enabled: boolean;
  save_all?: boolean;
  folder_path?: string;
  output_format?: string;
  background?: string;
  metadata?: Record<string, unknown>;
}

export interface PipelineAnalysisOptions {
  enabled: boolean;
  custom_prompt?: string;
}

export enum PipelineAction {
  GENERATE = 'generate',
  EDIT = 'edit',
}

export interface ImagePipelineRequest {
  action: PipelineAction;
  prompt: string;
  model?: string;
  n?: number;
  size?: string;
  response_format?: string;
  quality?: string;
  output_format?: string;
  output_compression?: number;
  background?: string;
  moderation?: string;
  user?: string;
  input_fidelity?: string;
  source_image_urls?: string[];
  source_image_base64?: string[];
  mask_image_url?: string;
  save_options: PipelineSaveOptions;
  analysis_options: PipelineAnalysisOptions;
  metadata?: Record<string, unknown>;
}

export interface ImagePipelineResponse {
  success: boolean;
  message: string;
  steps: PipelineStepResult[];
  generation?: ImageGenerationResponse;
  save?: ImageSaveResponse;
}

/**
 * Interface for metadata update response
 */
export interface MetadataUpdateResponse {
  success: boolean;
  message: string;
  updated: boolean;
}

/**
 * Interface for folder hierarchy
 */
export interface FolderHierarchy {
  [folderName: string]: {
    path: string;
    children: FolderHierarchy;
  };
}

/**
 * Fetch images from the gallery
 */
export async function fetchGalleryImages(
  limit: number = 50, 
  offset: number = 0,
  continuationToken?: string,
  prefix?: string,
  folderPath?: string
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
  if (folderPath) {
    params.append('folder_path', folderPath);
  }

  const url = `${API_BASE_URL}/gallery/images?${params.toString()}`;
  
  if (API_DEBUG) {
    console.log(`Fetching gallery images`);
    console.log(`GET ${url}`);
  }
  
  try {
    const response = await fetch(url);

    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch gallery images: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (API_DEBUG) {
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
  blobName: string
): Promise<{success: boolean, message: string}> {
  const params = new URLSearchParams();
  params.append('blob_name', blobName);
  params.append('media_type', 'image');

  const url = `${API_BASE_URL}/gallery/delete?${params.toString()}`;
  
  if (API_DEBUG) {
    console.log(`Deleting gallery asset: ${blobName}`);
    console.log(`DELETE ${url}`);
  }
  
  try {
    const response = await fetch(url, {
      method: 'DELETE'
    });

    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to delete gallery asset: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (API_DEBUG) {
      console.log('Response data:', data);
    }
    
    return data;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error(`Network error when deleting gallery asset: ${errorMessage}`);
    throw error;
  }
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
  
  if (API_DEBUG) {
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

    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to enhance image prompt: ${response.status} ${response.statusText}`);
    }

    const data: EnhancePromptResponse = await response.json();
    
    if (API_DEBUG) {
      console.log('Enhanced image prompt:', data.enhanced_prompt);
    }
    
    return data.enhanced_prompt;
  } catch (error) {
    console.error('Error enhancing image prompt:', error);
    throw error;
  }
}

/**
 * Generate images using DALL-E
 */
export async function runImagePipeline(
  request: ImagePipelineRequest,
  files?: {
    sourceImages?: File[];
    mask?: File | null;
  }
): Promise<ImagePipelineResponse> {
  const url = `${API_BASE_URL}/images/pipeline`;

  if (API_DEBUG) {
    console.log('Running image pipeline with payload:', request);
    console.log(`POST ${url}`);
  }

  const formData = new FormData();
  formData.append('payload', JSON.stringify(request));

  if (files?.sourceImages) {
    files.sourceImages.forEach((file) => {
      formData.append('source_images', file);
    });
  }

  if (files?.mask) {
    formData.append('mask', files.mask);
  }

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (API_DEBUG) {
    console.log(`Response status: ${response.status} ${response.statusText}`);
    if (!response.ok) {
      console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
    }
  }

  if (!response.ok) {
    throw new Error(`Failed to run image pipeline: ${response.status} ${response.statusText}`);
  }

  const data: ImagePipelineResponse = await response.json();

  if (API_DEBUG) {
    console.log('Pipeline response data:', data);
  }

  return data;
}

export async function generateImages(
  prompt: string, 
  n: number = 1,
  size: string = "1024x1024",
  response_format: string = "b64_json",
  background: string = "auto",
  outputFormat: string = "png",
  quality: string = "high",
  model: string = "gpt-image-2"
): Promise<ImageGenerationResponse> {
  const pipelineRequest: ImagePipelineRequest = {
    action: PipelineAction.GENERATE,
    prompt,
    model,
    n,
    size,
    response_format,
    background,
    output_format: outputFormat,
    quality,
    save_options: {
      enabled: false,
    },
    analysis_options: {
      enabled: false,
    },
  };

  try {
    const pipelineResponse = await runImagePipeline(pipelineRequest);
    if (!pipelineResponse.generation) {
      throw new Error('Pipeline response did not include generation data');
    }
    return pipelineResponse.generation;
  } catch (error) {
    console.error('Error generating images via pipeline:', error);
    throw error;
  }
}

/**
 * Save generated images to blob storage with optional analysis
 */
export async function saveGeneratedImages(
  generationResponse: ImageGenerationResponse,
  prompt: string,
  saveAll: boolean = true,
  folderPath: string = "",
  outputFormat: string = "png",
  model: string = "gpt-image-2",
  background: string = "auto",
  size: string = "1024x1024",
  analyze: boolean = false
): Promise<ImageSaveResponse> {
  const url = `${API_BASE_URL}/images/save`;
  
  if (API_DEBUG) {
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
    size,
    analyze
  };
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to save images: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (API_DEBUG) {
      console.log('Saved images response data:', data);
    }
    
    return data;
  } catch (error) {
    console.error('Error saving images:', error);
    throw error;
  }
}

/**
 * Unified image generation + analysis + saving
 */

export async function generateImagesWithAnalysis(params: {
  prompt: string;
  n?: number;
  size?: string;
  quality?: string;
  output_format?: string;
  output_compression?: number;
  background?: string;
  moderation?: string;
  user?: string;
  save_all?: boolean;
  folder_path?: string;
  model?: string;
  analyze?: boolean;
}): Promise<ImageSaveResponse> {
  const pipelineRequest: ImagePipelineRequest = {
    action: PipelineAction.GENERATE,
    prompt: params.prompt,
    model: params.model || 'gpt-image-2',
    n: params.n ?? 1,
    size: params.size || 'auto',
    response_format: 'b64_json',
    quality: params.quality || 'high',
    output_format: params.output_format || 'png',
    output_compression: params.output_compression,
    background: params.background || 'auto',
    moderation: params.moderation || 'auto',
    user: params.user,
    save_options: {
      enabled: true,
      save_all: params.save_all ?? true,
      folder_path: params.folder_path || '',
      output_format: params.output_format,
      background: params.background,
    },
    analysis_options: {
      enabled: params.analyze ?? true,
    },
  };

  if (API_DEBUG) {
    console.log('Generating images with analysis via pipeline');
    console.log('Payload:', pipelineRequest);
  }

  const pipelineResponse = await runImagePipeline(pipelineRequest);
  if (!pipelineResponse.save) {
    throw new Error('Pipeline response did not include save data');
  }
  return pipelineResponse.save;
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
  
  if (API_DEBUG) {
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
      
      if (API_DEBUG) {
        console.log(`Response status: ${response.status} ${response.statusText}`);
        if (!response.ok) {
          console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
        }
      }
      
      if (!response.ok) {
        throw new Error(`Failed to analyze image: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (API_DEBUG) {
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
 * Update asset metadata
 */
export async function updateAssetMetadata(
  blobName: string,
  metadata: AssetMetadata
): Promise<MetadataUpdateResponse> {
  // Extract asset ID from blob name (remove extension and folder path)
  const assetId = blobName.split('.')[0].split('/').pop();
  
  const params = new URLSearchParams();
  params.append('media_type', 'image');
  
  const url = `${API_BASE_URL}/metadata/${assetId}?${params.toString()}`;
  
  if (API_DEBUG) {
    console.log(`Updating metadata for asset: ${assetId} (blob: ${blobName})`);
    console.log(`PUT ${url}`);
    console.log('Metadata:', metadata);
  }
  
  try {
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(metadata),  // Send metadata directly, not wrapped
    });
    
    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }
    
    if (!response.ok) {
      throw new Error(`Failed to update metadata: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (API_DEBUG) {
      console.log('Response data:', data);
    }
    
    return data;
  } catch (error) {
    console.error('Error updating metadata:', error);
    throw error;
  }
}

/**
 * Fetch folders
 */
export async function fetchFolders(): Promise<{folders: string[], folder_hierarchy: FolderHierarchy}> {
  const url = `${API_BASE_URL}/gallery/folders?media_type=image`;
  
  if (API_DEBUG) {
    console.log(`Fetching folders`);
    console.log(`GET ${url}`);
  }
  
  try {
    const response = await fetch(url);
    
    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }
    
    if (!response.ok) {
      throw new Error(`Failed to fetch folders: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (API_DEBUG) {
      console.log('Folders response data:', data);
    }
    
    // Backend now returns simple string array
    // But keep compatibility check in case of old format
    interface LegacyFolder {
      folder_path?: string;
      id?: string;
    }
    
    const folderPaths = data.folders ? 
      (Array.isArray(data.folders) && data.folders.length > 0 && typeof data.folders[0] === 'string' 
        ? data.folders as string[]
        : data.folders.map((folder: string | LegacyFolder) => 
            typeof folder === 'string' ? folder : folder.folder_path || folder.id || ''
          )
      ) : [];
    
    return {
      folders: folderPaths,
      folder_hierarchy: data.folder_hierarchy || {}
    };
  } catch (error) {
    console.error('Error fetching folders:', error);
    throw error;
  }
}

/**
 * Create a new folder in the gallery
 */
export async function createFolder(
  folderPath: string
): Promise<{success: boolean, folder_path: string}> {
  const url = `${API_BASE_URL}/gallery/folders`;
  
  if (API_DEBUG) {
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
        media_type: 'image'
      }),
    });
    
    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }
    
    if (!response.ok) {
      throw new Error(`Failed to create folder: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (API_DEBUG) {
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
  targetFolder: string
): Promise<{success: boolean, message: string}> {
  const url = `${API_BASE_URL}/gallery/move`;
  
  if (API_DEBUG) {
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
        media_type: 'image',
        target_folder: targetFolder
      }),
    });
    
    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }
    
    if (!response.ok) {
      throw new Error(`Failed to move asset: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (API_DEBUG) {
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
 * Edit an image using the OpenAI API
 * 
 * @param sourceImages - File or array of files to edit
 * @param prompt - Text prompt describing the desired edits
 * @param n - Number of variations to generate (default: 1)
 * @param size - Output image size (default: "auto")
 * @param quality - Image quality setting (default: "high")
 * @param inputFidelity - Input fidelity for better reproduction of input features:
 *   - 'low' (default): Standard fidelity, faster processing
 *   - 'high': Better reproduction of input image features, additional cost (~$0.04-$0.06 per image)
 * @param model - Image generation model to use (default: "gpt-image-2")
 * @param outputFormat - Output format requested from the image model
 * @param background - Background handling requested from the image model
 */
export async function editImage(
  sourceImages: File | File[],
  prompt: string, 
  n: number = 1,
  size: string = "auto",
  quality: string = "high",
  inputFidelity: string = "low",
  model: string = "gpt-image-2",
  outputFormat: string = "png",
  background: string = "auto",
): Promise<ImageGenerationResponse> {
  if (inputFidelity && !["low", "high"].includes(inputFidelity)) {
    throw new Error("input_fidelity must be either 'low' or 'high'");
  }

  const filesArray = Array.isArray(sourceImages) ? sourceImages : [sourceImages];

  if (API_DEBUG) {
    console.log(`Editing ${filesArray.length} image(s) with prompt: ${prompt}, model: ${model}, input_fidelity: ${inputFidelity}`);
  }

  const pipelineRequest: ImagePipelineRequest = {
    action: PipelineAction.EDIT,
    prompt,
    model,
    n,
    size,
    response_format: 'b64_json',
    quality,
    output_format: outputFormat,
    background,
    input_fidelity: inputFidelity,
    save_options: {
      enabled: false,
    },
    analysis_options: {
      enabled: false,
    },
  };

  try {
    const pipelineResponse = await runImagePipeline(pipelineRequest, {
      sourceImages: filesArray,
    });

    if (!pipelineResponse.generation) {
      throw new Error('Pipeline response did not include generation data');
    }

    return pipelineResponse.generation;
  } catch (error) {
    console.error('Error editing image via pipeline:', error);
    throw error;
  }
}

/**
 * Analyze an image using a custom prompt
 */
interface CustomAnalysisRequestBody {
  custom_prompt: string;
  image_path?: string;
  base64_image?: string;
}

export async function analyzeImageCustom(
  imageUrl?: string,
  base64Image?: string, 
  customPrompt?: string,
  retries = 3
): Promise<ImageAnalysisResponse> {
  const url = `${API_BASE_URL}/images/analyze-custom`;
  
  if (!customPrompt || !customPrompt.trim()) {
    throw new Error("Custom prompt is required for custom analysis");
  }
  
  if (API_DEBUG) {
    console.log("Analyzing image with custom prompt:", customPrompt.substring(0, 100) + "...");
    console.log(`POST ${url}`);
  }
  
  let attempt = 0;
  let lastError: Error | null = null;
  
  while (attempt < retries) {
    try {
      attempt++;
      
      if (attempt > 1) {
        console.log(`Retry attempt ${attempt}/${retries} for custom image analysis`);
      }
      
      // Add a timeout to prevent hanging requests
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
      
      const requestBody: CustomAnalysisRequestBody = {
        custom_prompt: customPrompt
      };
      
      if (imageUrl) {
        requestBody.image_path = imageUrl;
      } else if (base64Image) {
        // Make sure the base64 string doesn't include the data URL prefix
        const cleanBase64 = base64Image.replace(/^data:image\/[a-z]+;base64,/, "");
        requestBody.base64_image = cleanBase64;
      } else {
        throw new Error("Either imageUrl or base64Image must be provided");
      }
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal
      });
      
      // Clear the timeout
      clearTimeout(timeoutId);
      
      if (API_DEBUG) {
        console.log(`Response status: ${response.status} ${response.statusText}`);
        if (!response.ok) {
          console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
        }
      }
      
      if (!response.ok) {
        throw new Error(`Failed to analyze image: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (API_DEBUG) {
        console.log('Custom analysis response data:', data);
      }
      
      return data;
    } catch (error) {
      console.error(`Custom image analysis attempt ${attempt}/${retries} failed:`, error);
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
  throw lastError || new Error("Custom image analysis failed after retries");
}

/**
 * Analyze an image using AI directly from base64 data
 */
export async function analyzeImageFromBase64(base64Image: string, retries = 3): Promise<ImageAnalysisResponse> {
  const url = `${API_BASE_URL}/images/analyze`;
  
  // Make sure the base64 string doesn't include the data URL prefix
  const cleanBase64 = base64Image.replace(/^data:image\/[a-z]+;base64,/, "");
  
  if (API_DEBUG) {
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
      
      if (API_DEBUG) {
        console.log(`Response status: ${response.status} ${response.statusText}`);
        if (!response.ok) {
          console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
        }
      }
      
      if (!response.ok) {
        throw new Error(`Failed to analyze image: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (API_DEBUG) {
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
 * Interface for brand protection request
 */
export interface BrandProtectionRequest {
  original_prompt: string;
  brands_to_protect: string;
  protection_mode: string;
}

/**
 * Interface for brand protection response
 */
export interface BrandProtectionResponse {
  enhanced_prompt: string;
}

/**
 * Protect an image prompt for brand safety
 */
export async function protectImagePrompt(
  prompt: string,
  brandsToProtect: string[],
  protectionMode: string
): Promise<string> {
  const url = `${API_BASE_URL}/images/prompt/protect`;
  
  if (API_DEBUG) {
    console.log(`Protecting image prompt: ${prompt}`);
    console.log(`Brands to protect: ${brandsToProtect.join(', ')}`);
    console.log(`Protection mode: ${protectionMode}`);
    console.log(`POST ${url}`);
  }
  
  // If brand protection is off or no brands to protect, just return the original prompt
  if (protectionMode === "off" || brandsToProtect.length === 0) {
    return prompt;
  }
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        original_prompt: prompt,
        brands_to_protect: brandsToProtect.join(', '),
        protection_mode: protectionMode
      }),
    });

    if (API_DEBUG) {
      console.log(`Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to protect image prompt: ${response.status} ${response.statusText}`);
    }

    const data: BrandProtectionResponse = await response.json();
    
    if (API_DEBUG) {
      console.log('Protected image prompt:', data.enhanced_prompt);
    }
    
    return data.enhanced_prompt;
  } catch (error) {
    console.error('Error protecting image prompt:', error);
    // If there's an error, return the original prompt
    return prompt;
  }
}
