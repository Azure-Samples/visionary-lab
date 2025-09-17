// Image service - handles all image-related API calls
import { API_BASE_URL, ImageSaveResponse as ApiImageSaveResponse, PipelineAction, runImagePipeline } from './api';
import type { ImageGenerationResponse, ImagePipelineRequest } from './api';

export type { ImageGenerationResponse } from './api';

interface PromptEnhancementResponse {
  enhanced_prompt: string;
}

/**
 * Edit an image via the unified image pipeline endpoint.
 */
export async function editImage(formData: FormData): Promise<ImageGenerationResponse> {
  const promptEntry = formData.get('prompt');
  if (!promptEntry || typeof promptEntry !== 'string') {
    throw new Error('Prompt is required for image editing');
  }

  const n = Number(formData.get('n') ?? '1');
  const size = String(formData.get('size') ?? 'auto');
  const model = String(formData.get('model') ?? 'gpt-image-1');
  const quality = String(formData.get('quality') ?? 'auto');
  const inputFidelity = String(formData.get('input_fidelity') ?? 'low');

  if (inputFidelity && !['low', 'high'].includes(inputFidelity)) {
    throw new Error("input_fidelity must be either 'low' or 'high'");
  }

  const sourceImages = formData
    .getAll('image')
    .filter((entry): entry is File => entry instanceof File);

  if (sourceImages.length === 0) {
    throw new Error('At least one source image is required for editing');
  }

  const maskEntry = formData.get('mask');
  const mask = maskEntry instanceof File ? maskEntry : null;

  const pipelineRequest: ImagePipelineRequest = {
    action: PipelineAction.EDIT,
    prompt: promptEntry,
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

  const pipelineResponse = await runImagePipeline(pipelineRequest, {
    sourceImages,
    mask,
  });

  if (!pipelineResponse.generation) {
    throw new Error('Pipeline response did not include generation data');
  }

  return pipelineResponse.generation;
}

/**
 * Save a generated image to the gallery
 */
export async function saveGeneratedImage(
  generationResponse: ImageGenerationResponse,
  options: {
    prompt?: string;
    model?: string;
    size?: string;
    background?: string;
    output_format?: string;
    save_all?: boolean;
    folder_path?: string;
    analyze?: boolean; // NEW: request backend analysis
    analyze?: boolean; // NEW: request backend analysis
  }
): Promise<ApiImageSaveResponse> {
  // Import the saveGeneratedImages function from api.ts
  const { saveGeneratedImages } = await import('./api');
  
  try {
    if (!generationResponse?.imgen_model_response?.data ||
        generationResponse.imgen_model_response.data.length === 0) {
      throw new Error('No image data found in generation response');
    }

    // Call the saveGeneratedImages function with the full generation response
    if (!generationResponse?.imgen_model_response?.data ||
        generationResponse.imgen_model_response.data.length === 0) {
      throw new Error('No image data found in generation response');
    }

    // Call the saveGeneratedImages function with the full generation response
    return await saveGeneratedImages(
      generationResponse,
      generationResponse,
      options.prompt || '',
      options.save_all || false,
      options.folder_path || '',
      options.output_format || 'png',
      options.model || 'gpt-image-1',
      options.background || 'auto',
      options.size || '1024x1024',
      options.analyze ?? true // default to true to match older behavior
      options.size || '1024x1024',
      options.analyze ?? true // default to true to match older behavior
    );
  } catch (error: unknown) {
    console.error('Error saving image:', error);
    throw new Error(`Failed to save image: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Enhance a prompt for better image generation results
 */
export async function enhancePrompt(originalPrompt: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/images/prompt/enhance`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      original_prompt: originalPrompt,
    }),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to enhance prompt: ${response.status} - ${errorText}`);
  }
  
  const data: PromptEnhancementResponse = await response.json();
  return data.enhanced_prompt;
}

/**
 * Extract base64 image data from a response
 */
export function getImageFromResponse(response: ImageGenerationResponse): string {
  if (!response.success || !response.imgen_model_response || !response.imgen_model_response.data || response.imgen_model_response.data.length === 0) {
    throw new Error('Invalid response from image generation API');
  }
  
  const imageData = response.imgen_model_response.data[0];
  
  if (imageData.b64_json) {
    return `data:image/png;base64,${imageData.b64_json}`;
  } else if (imageData.url) {
    return imageData.url;
  } else {
    throw new Error('No image data found in response');
  }
}

/**
 * Get token usage statistics from a response
 */
export function getTokenUsage(response: ImageGenerationResponse) {
  if (!response.token_usage) return null;
  
  return {
    total: response.token_usage.total_tokens,
    input: response.token_usage.input_tokens,
    output: response.token_usage.output_tokens,
  };
} 

