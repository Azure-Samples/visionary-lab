/**
 * API service for interacting with the backend API
 */

// API base URL configuration with GitHub Codespaces detection
const API_PROTOCOL = process.env.NEXT_PUBLIC_API_PROTOCOL || 'http';
const API_HOSTNAME = process.env.NEXT_PUBLIC_API_HOSTNAME || 'localhost';
// For GitHub Codespaces, port is part of the hostname, so this might be empty
const API_PORT = process.env.NEXT_PUBLIC_API_PORT || '8000';

// First build temporary base URL with conditional port inclusion
let API_BASE_URL = API_PORT 
  ? `${API_PROTOCOL}://${API_HOSTNAME}:${API_PORT}/api/v1` 
  : `${API_PROTOCOL}://${API_HOSTNAME}/api/v1`;

// Override with direct API URL if provided
if (process.env.NEXT_PUBLIC_API_URL) {
  console.log(`Overriding API URL with NEXT_PUBLIC_API_URL: ${process.env.NEXT_PUBLIC_API_URL}`);
  // Ensure API URL ends with /api/v1
  API_BASE_URL = process.env.NEXT_PUBLIC_API_URL.endsWith('/api/v1') 
    ? process.env.NEXT_PUBLIC_API_URL 
    : `${process.env.NEXT_PUBLIC_API_URL}/api/v1`;
}

// Export the final configured URL
export { API_BASE_URL };

// Log the configured API URL at startup to help debug connection issues
console.log(`API configured with: ${API_BASE_URL}`);
console.log('API environment variables:');
console.log(`- NEXT_PUBLIC_API_URL: ${process.env.NEXT_PUBLIC_API_URL || 'not set'}`);
console.log(`- NEXT_PUBLIC_API_PROTOCOL: ${process.env.NEXT_PUBLIC_API_PROTOCOL || 'not set'}`);
console.log(`- NEXT_PUBLIC_API_HOSTNAME: ${process.env.NEXT_PUBLIC_API_HOSTNAME || 'not set'}`);
console.log(`- NEXT_PUBLIC_API_PORT: ${process.env.NEXT_PUBLIC_API_PORT || 'not set'}`);

// Enable debug mode to log API requests
const API_DEBUG = process.env.NEXT_PUBLIC_DEBUG_MODE === 'true';

// Types for API requests and responses
export interface VideoGenerationRequest {
  prompt: string;
  n_variants: number;
  n_seconds: number;
  height: number;
  width: number;
  metadata?: Record<string, string>;
  // NEW: Optional source images for image+text to video
  sourceImages?: File[];
  // Optional direct fields for form usage
  folder_path?: string;
  analyze_video?: boolean;
  // Sora 2 NEW: Audio, Cameo, and Remix settings
  audio?: boolean;
  audio_language?: string;
  cameo?: string;
  remix_video_id?: string;
}

export interface VideoGenerationJob {
  id: string;
  status: string;
  prompt: string;
  n_variants: number;
  n_seconds: number;
  height: number;
  width: number;
  metadata?: Record<string, string>;
  generations?: Array<{
    id: string;
    job_id: string;
    created_at: number;
    width: number;
    height: number;
    n_seconds: number;
    prompt: string;
    url: string;
  }>;
  created_at?: number;
  finished_at?: number;
  failure_reason?: string;
}

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
 * Interface for video/image metadata
 */
export interface AssetMetadata {
  [key: string]: string | number | boolean | string[] | object | undefined;
  analysis?: {
    summary?: string;
    products?: string;
    tags?: string[];
    feedback?: string;
    analyzed_at?: string;
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
 * Create a new video generation job
 */
export async function createVideoGenerationJob(request: VideoGenerationRequest): Promise<VideoGenerationJob> {
  const url = `${API_BASE_URL}/videos/jobs`;
  
  if (API_DEBUG) {
    console.log(`Creating video generation job with prompt: ${request.prompt}`);
    console.log(`POST ${url}`);
    console.log('Request:', request);
  }

  // Always use multipart form data to match backend's Form/File signature
  const formData = new FormData();
  formData.append('prompt', request.prompt);
  formData.append('n_variants', String(request.n_variants));
  formData.append('n_seconds', String(request.n_seconds));
  formData.append('height', String(request.height));
  formData.append('width', String(request.width));

  // Derive folder_path from either explicit field or metadata.folder
  const folderPath = request.folder_path || request.metadata?.folder;
  if (folderPath) {
    formData.append('folder_path', folderPath);
  }

  // Derive analyze_video from explicit field or metadata.analyzeVideo
  const analyze = typeof request.analyze_video === 'boolean'
    ? request.analyze_video
    : (typeof request.metadata?.analyzeVideo === 'string' ? request.metadata?.analyzeVideo === 'true' : undefined);
  if (typeof analyze === 'boolean') {
    formData.append('analyze_video', String(analyze));
  }

  // Sora 2 NEW: Add audio generation parameters
  if (request.audio !== undefined) {
    formData.append('audio', String(request.audio));
  }
  if (request.audio_language) {
    formData.append('audio_language', request.audio_language);
  }
  
  // Sora 2 NEW: Add cameo reference
  if (request.cameo) {
    formData.append('cameo', request.cameo);
  }
  
  // Sora 2 NEW: Add remix video ID
  if (request.remix_video_id) {
    formData.append('remix_video_id', request.remix_video_id);
  }

  // Append images if provided
  if (request.sourceImages && request.sourceImages.length > 0) {
    for (const file of request.sourceImages) {
      formData.append('images', file, file.name);
    }
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
    throw new Error(`Failed to create video generation job: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  
  if (API_DEBUG) {
    console.log('Response data:', data);
  }
  
  return data;
}

/**
 * Get the status of a video generation job
 */
export async function getVideoGenerationJob(jobId: string): Promise<VideoGenerationJob> {
  const url = `${API_BASE_URL}/videos/jobs/${jobId}`;
  
  if (API_DEBUG) {
    console.log(`Fetching job status for job ${jobId}`);
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
      throw new Error(`Failed to get video generation job: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (API_DEBUG) {
      console.log('Response data:', data);
    }
    
    return data;
  } catch (error) {
    // Add better error logging and handling for connection issues
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    
    // Log the error but with a more descriptive message 
    console.error(`Network error when fetching job ${jobId}: ${errorMessage}`);
    
    // Re-throw the error for the caller to handle
    throw error;
  }
}

/**
 * Get the download URL for a video generation
 */
export function getVideoDownloadUrl(generationId: string, fileName: string): string {
  const url = `${API_BASE_URL}/videos/generations/${generationId}/content?file_name=${encodeURIComponent(fileName)}`;
  
  if (API_DEBUG) {
    console.log(`Video download URL: ${url}`);
  }
  
  return url;
}

/**
 * Get the download URL for a GIF generation
 */
export function getGifDownloadUrl(generationId: string, fileName: string): string {
  const url = `${API_BASE_URL}/videos/generations/${generationId}/content?file_name=${encodeURIComponent(fileName)}&as_gif=true`;
  
  if (API_DEBUG) {
    console.log(`GIF download URL: ${url}`);
  }
  
  return url;
}

/**
 * Download a video generation and return a local URL
 */
export async function downloadVideoGeneration(generationId: string, fileName: string): Promise<string> {
  const url = getVideoDownloadUrl(generationId, fileName);
  
  if (API_DEBUG) {
    console.log(`Downloading video generation ${generationId}`);
    console.log(`GET ${url}`);
  }
  
  const response = await fetch(url);

  if (API_DEBUG) {
    console.log(`Response status: ${response.status} ${response.statusText}`);
    if (!response.ok) {
      console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
    }
  }

  if (!response.ok) {
    throw new Error(`Failed to download video: ${response.status} ${response.statusText}`);
  }

  // Create a blob URL for the video
  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  
  if (API_DEBUG) {
    console.log(`Created blob URL: ${blobUrl}`);
  }
  
  return blobUrl;
}

/**
 * Upload a video to the gallery
 */
export async function uploadVideoToGallery(
  videoBlob: Blob, 
  fileName: string, 
  metadata: AssetMetadata,
  folder?: string,
  uniqueId?: string
): Promise<GalleryUploadResponse> {
  const url = `${API_BASE_URL}/gallery/upload`;
  const logId = uniqueId || `upload-${Date.now().toString().substring(6)}`;
  
  if (API_DEBUG) {
    console.log(`[${logId}] Uploading video to gallery: ${fileName} (${videoBlob.size} bytes)`);
    console.log(`[${logId}] POST ${url}`);
    console.log(`[${logId}] Metadata:`, metadata);
    if (folder) {
      console.log(`[${logId}] Target folder: ${folder}`);
    }
  }

  // Create form data for the upload
  const formData = new FormData();
  formData.append('file', videoBlob, fileName);
  formData.append('media_type', 'video');
  
  // Add metadata as JSON string
  if (metadata) {
    formData.append('metadata', JSON.stringify(metadata));
  }
  
  // Add folder path if specified
  if (folder && folder !== 'root') {
    formData.append('folder_path', folder);
  }
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (API_DEBUG) {
      console.log(`[${logId}] Response status: ${response.status} ${response.statusText}`);
      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Could not read error response');
        console.error(`[${logId}] Upload failed: ${errorText}`);
      }
    }

    if (!response.ok) {
      throw new Error(`Failed to upload video to gallery: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (API_DEBUG) {
      console.log(`[${logId}] Upload successful. Response data:`, data);
    }
    
    return data;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error(`[${logId}] Error uploading video: ${errorMessage}`);
    throw error;
  }
}

/**
 * Separate two-step process: First download the video, then upload it to the gallery
 * This addresses the issue with the combined endpoint by separating concerns
 */
export async function downloadThenUploadToGallery(
  generationId: string, 
  fileName: string, 
  metadata: AssetMetadata,
  folder?: string
): Promise<{blobUrl: string, uploadResponse: GalleryUploadResponse}> {
  const uniqueId = `upload-${generationId}-${Date.now().toString().substring(6)}`;
  
  if (API_DEBUG) {
    console.log(`[${uniqueId}] Two-step download and upload for generation ${generationId}`);
    if (folder) {
      console.log(`[${uniqueId}] Target folder: ${folder}`);
    }
    console.log(`[${uniqueId}] Metadata:`, metadata);
  }
  
  // Step 1: Download the video
  const downloadUrl = getVideoDownloadUrl(generationId, fileName);
  
  if (API_DEBUG) {
    console.log(`[${uniqueId}] Step 1: Downloading video - GET ${downloadUrl}`);
  }
  
  try {
    const response = await fetch(downloadUrl);

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Could not read error response');
      console.error(`[${uniqueId}] Download failed with status ${response.status}: ${errorText}`);
      throw new Error(`Failed to download video: ${response.status} ${response.statusText}`);
    }

    // Get the video blob
    const blob = await response.blob();
    
    // Create a blob URL for display
    const blobUrl = URL.createObjectURL(blob);
    
    if (API_DEBUG) {
      console.log(`[${uniqueId}] Successfully downloaded ${blob.size} bytes`);
      console.log(`[${uniqueId}] Created blob URL: ${blobUrl}`);
      console.log(`[${uniqueId}] Step 2: Uploading to gallery`);
    }
    
    // Step 2: Upload to gallery using the updated uploadVideoToGallery function
    const uploadResponse = await uploadVideoToGallery(blob, fileName, metadata, folder, uniqueId);
    
    if (API_DEBUG) {
      console.log(`[${uniqueId}] Upload successful. Blob name: ${uploadResponse.blob_name}`);
    }
    
    return { blobUrl, uploadResponse };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error(`[${uniqueId}] Error in downloadThenUploadToGallery: ${errorMessage}`);
    throw error;
  }
}

/**
 * Helper function to generate a filename from a prompt and ID.
 * Sanitizes the prompt to be filesystem-friendly.
 */
export function generateVideoFilename(prompt: string, generationId: string, extension: string = ".mp4"): string {
  // Take first 50 chars of prompt, or full prompt if shorter
  const promptPart = prompt.substring(0, 50).trim();
  // Replace newlines and multiple whitespace with single space first
  const normalizedPrompt = promptPart.replace(/\s+/g, ' ');
  // Replace non-alphanumeric characters (except spaces, underscores, hyphens) with underscore
  const sanitizedPrompt = normalizedPrompt.replace(/[^a-zA-Z0-9 _-]/g, '_').replace(/\s+/g, '_');
  // Remove multiple consecutive underscores and trim underscores from ends
  const cleanedPrompt = sanitizedPrompt.replace(/_+/g, '_').replace(/^_+|_+$/g, '');
  // Ensure it's not empty after sanitization
  const finalPromptPart = cleanedPrompt || "video";
  return `${finalPromptPart}_${generationId}${extension}`;
}

/**
 * Helper function to map video settings to API request
 */
export function mapSettingsToApiRequest(settings: {
  prompt: string;
  resolution: string;
  duration: string; // e.g., "5s"
  aspectRatio: string; // e.g., "16:9"
  fps?: number; // Optional FPS
  // Sora 2 NEW
  selectedCameo?: string | null;
  remixVideoId?: string | null;
}): VideoGenerationRequest {
  // Parse duration (e.g., "5s" to 5)
  const n_seconds = parseInt(settings.duration, 10) || 5; // Default to 5 if parsing fails

  let width: number;
  let height: number;

  const res = settings.resolution;
  const ar = settings.aspectRatio;

  if (ar === "16:9") {
    if (res === "1080p") { width = 1792; height = 1024; }
    else { width = 1280; height = 720; }
  } else if (ar === "9:16") {
    if (res === "1080p") { width = 1024; height = 1792; }
    else { width = 720; height = 1280; }
  } else if (ar === "1:1") {
    width = 1280; height = 720;
    console.warn(`1:1 aspect ratio not supported by Sora 2, using 16:9 (1280x720)`);
  } else {
    width = 1280;
    height = 720;
    console.warn(`Unexpected aspectRatio: ${ar}, defaulting to 1280x720 (Sora 2 standard)`);
  }

  return {
    prompt: settings.prompt,
    n_variants: 1,
    n_seconds,
    height,
    width,
    // fps: settings.fps, // Assuming backend doesn't support fps yet or it's handled differently
    // Sora 2 NEW: Cameo and Remix settings
    cameo: settings.selectedCameo || undefined,
    remix_video_id: settings.remixVideoId || undefined,
  };
}

/**
 * List video generation jobs
 */
export async function listVideoGenerationJobs(limit: number = 50): Promise<VideoGenerationJob[]> {
  const url = `${API_BASE_URL}/videos/jobs?limit=${limit}`;
  
  if (API_DEBUG) {
    console.log(`Listing video generation jobs with limit ${limit}`);
    console.log(`GET ${url}`);
  }
  
  const response = await fetch(url);

  if (API_DEBUG) {
    console.log(`Response status: ${response.status} ${response.statusText}`);
    if (!response.ok) {
      console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
    }
  }

  if (!response.ok) {
    throw new Error(`Failed to list video generation jobs: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  
  if (API_DEBUG) {
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

  const url = `${API_BASE_URL}/gallery/videos?${params.toString()}`;
  
  if (API_DEBUG) {
    console.log(`Fetching gallery videos`);
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
      throw new Error(`Failed to fetch gallery videos: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    if (API_DEBUG) {
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
  blobName: string, 
  mediaType: MediaType
): Promise<{success: boolean, message: string}> {
  const params = new URLSearchParams();
  params.append('blob_name', blobName);
  params.append('media_type', mediaType);

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

/**
 * Interface for video analysis response
 */
export interface VideoAnalysisResponse {
  summary: string;
  products: string;
  tags: string[];
  feedback: string;
}

export interface VideoGenerationWithAnalysisRequest {
  prompt: string;
  n_variants: number;
  n_seconds: number;
  height: number;
  width: number;
  analyze_video: boolean;
  metadata?: Record<string, string>;
  // NEW: Optional source images for image+text
  sourceImages?: File[];
}

export interface VideoGenerationWithAnalysisResponse {
  job: VideoGenerationJob;
  analysis_results?: VideoAnalysisResponse[];
  upload_results?: Array<{[key: string]: string}>;
}

/**
 * Analyze a video using AI
 */
export async function analyzeVideo(videoName: string, retries = 3): Promise<VideoAnalysisResponse> {
  const url = `${API_BASE_URL}/videos/analyze`;
  
  if (API_DEBUG) {
    console.log(`Analyzing video with name: ${videoName}`);
    console.log(`POST ${url}`);
  }
  
  let attempt = 0;
  let lastError: Error | null = null;
  
  try {
    // First, get the SAS tokens to construct the full URL properly
    const sasTokensResponse = await fetch(`${API_BASE_URL}/gallery/sas-tokens`);
    
    if (!sasTokensResponse.ok) {
      throw new Error(`Failed to get SAS tokens: ${sasTokensResponse.status} ${sasTokensResponse.statusText}`);
    }
    
    const sasTokens = await sasTokensResponse.json();
    
    // Check if we have the video container URL
    if (!sasTokens.video_container_url) {
      console.error('Missing required video_container_url from SAS tokens:', sasTokens);
      throw new Error('Missing required video container URL from SAS tokens');
    }
    
    // Use the actual video_container_url from the SAS tokens response
    const videoContainerUrl = sasTokens.video_container_url;
    const videoSasToken = sasTokens.video_sas_token;
    
    // Construct a proper Azure blob storage URL
    const videoPath = `${videoContainerUrl}/${videoName}${videoSasToken ? `?${videoSasToken}` : ''}`;
    
    if (API_DEBUG) {
      console.log(`Constructed video path for analysis: ${videoPath}`);
    }
    
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
        
        if (API_DEBUG) {
          console.log(`Response status: ${response.status} ${response.statusText}`);
          if (!response.ok) {
            console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
          }
        }
        
        if (!response.ok) {
          throw new Error(`Failed to analyze video: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (API_DEBUG) {
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
  } catch (error) {
    console.error('Error in analyzeVideo:', error);
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
 * Enhance a prompt using the backend API (for videos)
 */
export async function enhancePrompt(prompt: string): Promise<string> {
  const url = `${API_BASE_URL}/videos/prompt/enhance`;
  
  if (API_DEBUG) {
    console.log(`Enhancing video prompt: ${prompt}`);
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
      throw new Error(`Failed to enhance video prompt: ${response.status} ${response.statusText}`);
    }

    const data: EnhancePromptResponse = await response.json();
    
    if (API_DEBUG) {
      console.log('Enhanced video prompt:', data.enhanced_prompt);
    }
    
    return data.enhanced_prompt;
  } catch (error) {
    console.error('Error enhancing video prompt:', error);
    throw error;
  }
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
  quality: string = "auto",
  model: string = "gpt-image-1"
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
  model: string = "gpt-image-1",
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
    model: params.model || 'gpt-image-1',
    n: params.n ?? 1,
    size: params.size || 'auto',
    response_format: 'b64_json',
    quality: params.quality || 'auto',
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
  mediaType: MediaType,
  metadata: AssetMetadata
): Promise<MetadataUpdateResponse> {
  // Extract asset ID from blob name (remove extension and folder path)
  const assetId = blobName.split('.')[0].split('/').pop();
  
  const params = new URLSearchParams();
  params.append('media_type', mediaType);
  
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
export async function fetchFolders(
  mediaType?: MediaType
): Promise<{folders: string[], folder_hierarchy: FolderHierarchy}> {
  let url = `${API_BASE_URL}/gallery/folders`;
  
  if (mediaType) {
    url += `?media_type=${mediaType}`;
  }
  
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
  folderPath: string,
  mediaType: MediaType = MediaType.IMAGE
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
        media_type: mediaType
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
  targetFolder: string,
  mediaType: MediaType
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
        media_type: mediaType,
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
 * @param quality - Image quality setting (default: "auto")
 * @param inputFidelity - Input fidelity for better reproduction of input features:
 *   - 'low' (default): Standard fidelity, faster processing
 *   - 'high': Better reproduction of input image features, additional cost (~$0.04-$0.06 per image)
 * @param model - Image generation model to use (default: "gpt-image-1")
 */
export async function editImage(
  sourceImages: File | File[],
  prompt: string, 
  n: number = 1,
  size: string = "auto",
  quality: string = "auto",
  inputFidelity: string = "low",
  model: string = "gpt-image-1"
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

/**
 * Create a video generation job with optional analysis in one atomic operation
 */
export async function createVideoGenerationWithAnalysis(request: VideoGenerationWithAnalysisRequest): Promise<VideoGenerationWithAnalysisResponse> {
  const url = `${API_BASE_URL}/videos/generate-with-analysis`;
  
  if (API_DEBUG) {
    console.log(`Creating video generation with analysis: ${request.prompt}`);
    console.log(`POST ${url}`);
    console.log('Request:', request);
  }

  // If images are present, prefer the multipart unified endpoint
  if (request.sourceImages && request.sourceImages.length > 0) {
    return await createVideoGenerationWithAnalysisMultipart(request);
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (API_DEBUG) {
    console.log(`Response status: ${response.status} ${response.statusText}`);
    if (!response.ok) {
      console.error('Error response:', await response.text().catch(() => 'Could not read response text'));
    }
  }

  if (!response.ok) {
    throw new Error(`Failed to create video generation with analysis: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  
  if (API_DEBUG) {
    console.log('Response data:', data);
  }
  
  return data;
}

/**
 * Unified multipart variant that supports optional images
 */
export async function createVideoGenerationWithAnalysisMultipart(request: VideoGenerationWithAnalysisRequest): Promise<VideoGenerationWithAnalysisResponse> {
  const url = `${API_BASE_URL}/videos/generate-with-analysis/upload`;

  if (API_DEBUG) {
    console.log(`Creating video (multipart) with analysis: ${request.prompt}`);
    console.log(`POST ${url}`);
  }

  const formData = new FormData();
  formData.append('prompt', request.prompt);
  formData.append('n_variants', String(request.n_variants));
  formData.append('n_seconds', String(request.n_seconds));
  formData.append('height', String(request.height));
  formData.append('width', String(request.width));
  formData.append('analyze_video', String(request.analyze_video));

  // Provide folder via dedicated field for backend convenience
  const folderFromMeta = request.metadata?.folder;
  if (folderFromMeta) {
    formData.append('folder_path', folderFromMeta);
  }

  // Include metadata JSON if present
  if (request.metadata) {
    formData.append('metadata', JSON.stringify(request.metadata));
  }

  if (request.sourceImages && request.sourceImages.length > 0) {
    for (const file of request.sourceImages) {
      formData.append('images', file, file.name);
    }
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
    throw new Error(`Failed to create video generation with analysis (multipart): ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  return data;
}

/**
 * Analyze a video and save the analysis results to the video's metadata
 * This combines analyzing the video and updating its metadata in a single workflow
 */
export async function analyzeAndUpdateVideoMetadata(videoName: string): Promise<{
  analysis: VideoAnalysisResponse;
  metadata: MetadataUpdateResponse;
}> {
  if (API_DEBUG) {
    console.log(`Analyzing video and updating metadata for: ${videoName}`);
  }
  
  try {
    // Step 1: Analyze the video
    const analysis = await analyzeVideo(videoName);
    
    if (!analysis) {
      throw new Error("Failed to analyze video: No analysis result returned");
    }
    
    if (API_DEBUG) {
      console.log("Video analysis complete, updating metadata...");
    }
    
    // Step 2: Prepare metadata update with analysis results using nested structure
    const metadata: AssetMetadata = {
      analysis: {
        summary: analysis.summary,
        products: analysis.products,
        tags: analysis.tags,
        feedback: analysis.feedback,
        analyzed_at: new Date().toISOString()
      },
      has_analysis: true
    };
    
    // Step 3: Update the video's metadata
    const metadataResult = await updateAssetMetadata(videoName, MediaType.VIDEO, metadata);
    
    if (API_DEBUG) {
      console.log("Metadata update complete");
    }
    
    return {
      analysis,
      metadata: metadataResult
    };
  } catch (error) {
    console.error("Error in analyzeAndUpdateVideoMetadata:", error);
    throw error;
  }
} 

// --- SSE Streaming Types and Functions ---

/**
 * Event types for video generation SSE stream
 */
export type VideoStreamEventType = 'status' | 'created' | 'progress' | 'processing' | 'complete' | 'error';

/**
 * Base interface for SSE events
 */
export interface VideoStreamEventBase {
  type: VideoStreamEventType;
}

export interface VideoStreamStatusEvent extends VideoStreamEventBase {
  type: 'status';
  step: string;
  message: string;
}

export interface VideoStreamCreatedEvent extends VideoStreamEventBase {
  type: 'created';
  job_id: string;
  status: string;
}

export interface VideoStreamProgressEvent extends VideoStreamEventBase {
  type: 'progress';
  status: string;
  progress: number;
  elapsed: number;
}

export interface VideoStreamProcessingEvent extends VideoStreamEventBase {
  type: 'processing';
  step: 'downloading' | 'analyzing' | 'uploading';
  generation_id?: string;
}

export interface VideoStreamCompleteEvent extends VideoStreamEventBase {
  type: 'complete';
  job: VideoGenerationJob;
  analysis_results?: VideoAnalysisResponse[];
}

export interface VideoStreamErrorEvent extends VideoStreamEventBase {
  type: 'error';
  error: string;
}

export type VideoStreamEvent = 
  | VideoStreamStatusEvent
  | VideoStreamCreatedEvent
  | VideoStreamProgressEvent
  | VideoStreamProcessingEvent
  | VideoStreamCompleteEvent
  | VideoStreamErrorEvent;

/**
 * Callback function type for SSE events
 */
export type VideoStreamEventCallback = (event: VideoStreamEvent) => void;

/**
 * Stream video generation with analysis using Server-Sent Events.
 * Provides real-time progress updates without blocking the server.
 * 
 * @param request The video generation request parameters
 * @param onEvent Callback function called for each SSE event
 * @returns A cleanup function to abort the stream
 */
export function streamVideoGenerationWithAnalysis(
  request: VideoGenerationWithAnalysisRequest,
  onEvent: VideoStreamEventCallback
): () => void {
  const url = `${API_BASE_URL}/videos/generate-with-analysis/stream`;
  
  if (API_DEBUG) {
    console.log(`Starting SSE stream for video generation with analysis`);
    console.log(`POST ${url}`);
    console.log('Request:', request);
  }

  // Build FormData for the request
  const formData = new FormData();
  formData.append('prompt', request.prompt);
  formData.append('n_seconds', String(request.n_seconds));
  formData.append('height', String(request.height));
  formData.append('width', String(request.width));
  formData.append('analyze_video', String(request.analyze_video));
  
  // Add folder path from metadata if present
  const folderPath = request.metadata?.folder;
  if (folderPath) {
    formData.append('folder_path', folderPath);
  }
  
  // Add metadata JSON if present
  if (request.metadata) {
    formData.append('metadata', JSON.stringify(request.metadata));
  }
  
  // Add images if present
  if (request.sourceImages && request.sourceImages.length > 0) {
    for (const file of request.sourceImages) {
      formData.append('images', file, file.name);
    }
  }

  // Create AbortController for cleanup
  const abortController = new AbortController();

  // Use fetch with ReadableStream to handle SSE from POST request
  // (EventSource only supports GET requests)
  fetch(url, {
    method: 'POST',
    body: formData,
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errorText = await response.text();
        onEvent({ type: 'error', error: `HTTP ${response.status}: ${errorText}` });
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onEvent({ type: 'error', error: 'No response body' });
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          if (API_DEBUG) {
            console.log('SSE stream ended');
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        
        // Parse SSE events from buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        let currentEventType: string | null = null;
        let currentData: string | null = null;

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            currentData = line.slice(6);
          } else if (line === '' && currentEventType && currentData) {
            // End of event, parse and dispatch
            try {
              const parsedData = JSON.parse(currentData);
              const event: VideoStreamEvent = {
                type: currentEventType as VideoStreamEventType,
                ...parsedData,
              };
              
              if (API_DEBUG) {
                console.log('SSE event:', event);
              }
              
              onEvent(event);
            } catch (parseError) {
              console.error('Failed to parse SSE data:', currentData, parseError);
            }
            
            currentEventType = null;
            currentData = null;
          }
        }
      }
    })
    .catch((error) => {
      if (error.name === 'AbortError') {
        if (API_DEBUG) {
          console.log('SSE stream aborted by user');
        }
        return;
      }
      console.error('SSE stream error:', error);
      onEvent({ type: 'error', error: error.message || 'Stream error' });
    });

  // Return cleanup function
  return () => {
    if (API_DEBUG) {
      console.log('Aborting SSE stream');
    }
    abortController.abort();
  };
} 
