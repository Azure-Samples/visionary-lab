import { GalleryItem, fetchGalleryImages } from "@/services/api";
import { sasTokenService } from "@/services/sas-token";

function getOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}
/**
 * Convert GalleryItem to ImageMetadata
 */
async function mapGalleryItemToImageMetadata(item: GalleryItem): Promise<ImageMetadata> {
  try {
    const normalizeToString = (value: unknown): string => {
      if (typeof value === 'string') return value;
      if (Array.isArray(value)) {
        return value
          .map((entry) => {
            if (typeof entry === 'string') return entry;
            if (entry && typeof entry === 'object') {
              const objectValues = Object.values(entry as Record<string, unknown>)
                .filter((val) => typeof val === 'string' && val.trim().length > 0) as string[];
              if (objectValues.length > 0) {
                return objectValues.join(' ');
              }
            }
            return entry != null ? String(entry) : '';
          })
          .filter((entry) => entry && entry.trim().length > 0)
          .join(', ');
      }
      if (value && typeof value === 'object') {
        const objectValues = Object.values(value as Record<string, unknown>)
          .filter((val) => typeof val === 'string' && val.trim().length > 0) as string[];
        if (objectValues.length > 0) {
          return objectValues.join(', ');
        }
      }
      return value != null ? String(value) : '';
    };

    const normalizeTags = (value: unknown): string[] => {
      if (Array.isArray(value)) {
        return value
          .map((tag) => {
            if (typeof tag === 'string') {
              return tag.trim();
            }
            if (tag && typeof tag === 'object') {
              const possibleName =
                (tag as Record<string, unknown>).name ??
                (tag as Record<string, unknown>).label ??
                (tag as Record<string, unknown>).title;
              if (typeof possibleName === 'string') {
                return possibleName.trim();
              }
              return normalizeToString(tag);
            }
            return '';
          })
          .filter((tag) => tag.length > 0);
      }

      if (typeof value === 'string') {
        return value
          .split(/[,;]+/)
          .map((tag) => tag.trim())
          .filter((tag) => tag.length > 0);
      }

      return [];
    };

    // Extract title from prompt (preferred) or name
    const title = item.metadata?.prompt || item.name.split('.')[0].replace(/_/g, ' ');

    // Extract description from CosmosDB metadata, falling back to prompt-derived text
    const descriptionSource = item.metadata?.analysis?.summary ?? item.metadata?.description ?? '';
    const description = normalizeToString(descriptionSource);

    // Use a direct SAS token URL for the image
    const src = await sasTokenService.getBlobUrl(item.name);
    console.log(`Using direct blob URL for ${item.name}`);

    // Extract tags from CosmosDB analysis structure
    const tags = normalizeTags(item.metadata?.analysis?.tags ?? item.metadata?.tags);

    // Extract analysis results from CosmosDB nested structure
    let analysis: ImageMetadata['analysis'] = undefined;
    if (item.metadata?.analysis) {
      const analysisData = item.metadata.analysis;
      analysis = {
        summary: normalizeToString(analysisData.summary),
        products: normalizeToString(analysisData.products),
        feedback: normalizeToString(analysisData.feedback),
        tags: normalizeTags(analysisData.tags),
        analyzed: item.metadata.has_analysis === true || analysisData.analyzed === true,
      };
    }

    return {
      id: item.id,
      name: item.name,
      src,
      title: title.charAt(0).toUpperCase() + title.slice(1),
      description,
      width: getOptionalNumber(item.metadata?.width),
      height: getOptionalNumber(item.metadata?.height),
      tags,
      size: "medium" as const,
      originalItem: item,
      analysis,
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
  analysis?: {
    summary?: string;
    products?: string;
    feedback?: string;
    tags?: string[];
    analyzed?: boolean;
  };
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
      
      const imageItems = response.items;
      
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
    throw error;
  }
} 
