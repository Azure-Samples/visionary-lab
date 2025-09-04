import { fetchGalleryVideos, GalleryItem, MediaType, fetchGalleryImages } from "@/services/api";
import { sasTokenService } from "@/services/sas-token";

export interface VideoMetadata {
  src: string;
  title: string;
  description?: string;
  size: "small" | "medium" | "large";
  id: string;
  name: string;
  tags?: string[];
  originalItem: GalleryItem;
  width?: number;
  height?: number;
  // Analysis metadata from Azure Blob Storage
  analysis?: {
    summary?: string;
    products?: string;
    tags?: string[];
    feedback?: string;
    analyzed?: boolean;
  };
}

/**
 * Convert GalleryItem to VideoMetadata
 */
async function mapGalleryItemToVideoMetadata(item: GalleryItem): Promise<VideoMetadata> {
  // Extract title from metadata or name
  const title = item.metadata?.title || item.name.split('.')[0].replace(/_/g, ' ');
  
  // Extract prompt from metadata - prioritize prompt over description
  const description = item.metadata?.prompt || item.metadata?.description || '';
  
  // Get direct URL with SAS token
  const src = await sasTokenService.getBlobUrl(item.name, item.media_type === MediaType.VIDEO);
  console.log(`Using direct blob URL for ${item.name}`);
  
  // Extract analysis metadata if available
  let analysis: VideoMetadata['analysis'] = undefined;
  if (item.metadata) {
    const hasAnalysis = item.metadata.summary || item.metadata.products || item.metadata.tags || item.metadata.feedback;
    if (hasAnalysis) {
      analysis = {
        summary: item.metadata.summary as string,
        products: item.metadata.products as string,
        feedback: item.metadata.feedback as string,
        analyzed: item.metadata.analyzed === 'true' || item.metadata.analyzed === true,
      };
      
      // Parse tags from metadata - they might be stored as comma-separated string
      if (item.metadata.tags) {
        if (typeof item.metadata.tags === 'string') {
          analysis.tags = item.metadata.tags.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0);
        } else if (Array.isArray(item.metadata.tags)) {
          analysis.tags = item.metadata.tags;
        }
      }
    }
  }

  return {
    id: item.id,
    name: item.name,
    src,
    title: title.charAt(0).toUpperCase() + title.slice(1), // Capitalize first letter
    description: description,
    // We'll assign the size later in a structured way
    size: "medium", // Default size, will be overridden
    originalItem: item,
    analysis,
  };
}

/**
 * Assign sizes to videos in a structured pattern to create a visually interesting grid
 */
function assignVideoSizes(videos: VideoMetadata[]): VideoMetadata[] {
  return videos.map((video, index) => {
    // Create a structured pattern of sizes
    // Every 5th video is large, every 3rd is small, the rest are medium
    let size: "small" | "medium" | "large" = "medium";
    
    if (index % 5 === 0) {
      size = "large";
    } else if (index % 3 === 0) {
      size = "small";
    }
    
    return {
      ...video,
      size
    };
  });
}

/**
 * Fetch videos from the gallery API
 */
export async function fetchVideos(
  limit: number = 50, 
  offset: number = 0,
  folderPath?: string
): Promise<VideoMetadata[]> {
  try {
    // Try to fetch videos from the API
    const response = await fetchGalleryVideos(limit, offset, undefined, undefined, folderPath);
    
    if (response.success && response.items.length > 0) {
      // Map items to metadata with Promise.all to handle async mapping
      const videoItemPromises = response.items
        .filter(item => item.media_type === MediaType.VIDEO)
        .map((item) => mapGalleryItemToVideoMetadata(item));
      
      const videoItems = await Promise.all(videoItemPromises);
      
      // Assign sizes in a structured way
      return assignVideoSizes(videoItems);
    } else {
      console.warn("No videos found in gallery API");
      return []; // Return empty array instead of mock videos
    }
  } catch (error) {
    console.error("Error fetching videos from gallery API:", error);
    return []; // Return empty array instead of mock videos
  }
}

/**
 * Convert GalleryItem to ImageMetadata
 */
async function mapGalleryItemToImageMetadata(item: GalleryItem): Promise<ImageMetadata> {
  try {
    // Extract title from metadata or name
    const title = item.metadata?.title || item.name.split('.')[0].replace(/_/g, ' ');
    
    // Extract description from metadata
    const description = item.metadata?.description || '';
    
    // Use direct SAS token URL (false for images, true for videos)
    const src = await sasTokenService.getBlobUrl(item.name, false);
    console.log(`Using direct blob URL for ${item.name}`);
    
    return {
      id: item.id,
      name: item.name,
      src,
      title: title.charAt(0).toUpperCase() + title.slice(1),
      description: description,
      width: item.metadata?.width ? parseInt(item.metadata.width) : undefined,
      height: item.metadata?.height ? parseInt(item.metadata.height) : undefined,
      tags: [],
      size: "medium" as const,
      originalItem: item,
    };
  } catch (error) {
    console.error(`Error mapping gallery item ${item.id}:`, error);
    throw error;
  }
}

/**
 * Interface for image metadata
 */
export interface ImageMetadata {
  src: string;
  title: string;
  description?: string;
  id: string;
  name: string;
  tags?: string[];
  originalItem: GalleryItem;
  width?: number;
  height?: number;
  size: "small" | "medium" | "large";
}

/**
 * Assign sizes to images based on dimensions or in a structured pattern
 */
function assignImageSizes(images: ImageMetadata[]): ImageMetadata[] {
  return images.map((image, index) => {
    // If we have width and height, use them to determine size
    if (image.width && image.height) {
      const ratio = image.width / image.height;
      
      if (ratio > 1.5) {
        return { ...image, size: "large" }; // Wide images
      } else if (ratio < 0.7) {
        return { ...image, size: "small" }; // Tall images
      } else {
        return { ...image, size: "medium" }; // Square-ish images
      }
    }
    
    // Fall back to alternating pattern based on index
    let size: "small" | "medium" | "large" = "medium";
    
    if (index % 5 === 0) {
      size = "large";
    } else if (index % 3 === 0) {
      size = "small";
    }
    
    return { ...image, size };
  });
}

/**
 * Fetch images from the gallery API
 */
export async function fetchImages(
  limit: number = 50, 
  offset: number = 0,
  folderPath?: string
): Promise<ImageMetadata[]> {
  try {
    console.log(`Fetching images: limit=${limit}, offset=${offset}, folderPath=${folderPath}`);
    
    // Try to fetch images from the API
    const response = await fetchGalleryImages(limit, offset, undefined, undefined, folderPath);
    
    if (response.success && response.items.length > 0) {
      console.log(`Received ${response.items.length} items from gallery API`);
      
      // Filter for images only
      const imageItems = response.items.filter(item => item.media_type === MediaType.IMAGE);
      console.log(`Filtered to ${imageItems.length} image items`);
      
      if (imageItems.length === 0) {
        console.warn("No image items found after filtering");
        return [];
      }
      
      // Map items to metadata with Promise.allSettled to handle individual failures
      const imageItemPromises = imageItems.map(async (item, index) => {
        try {
          const metadata = await mapGalleryItemToImageMetadata(item);
          console.log(`Successfully mapped item ${index + 1}/${imageItems.length}: ${item.name}`);
          return metadata;
        } catch (error) {
          console.error(`Failed to map item ${item.name}:`, error);
          return null;
        }
      });
      
      const results = await Promise.allSettled(imageItemPromises);
      const successfulItems = results
        .filter((result): result is PromiseFulfilledResult<ImageMetadata> => 
          result.status === 'fulfilled' && result.value !== null
        )
        .map(result => result.value);
      
      console.log(`Successfully processed ${successfulItems.length}/${imageItems.length} images`);
      
      // Assign sizes in a structured way
      return assignImageSizes(successfulItems);
    } else {
      console.warn("No images found in gallery API response", { success: response.success, itemCount: response.items.length });
      return [];
    }
  } catch (error) {
    console.error("Error fetching images from gallery API:", error);
    return [];
  }
} 