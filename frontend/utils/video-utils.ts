/**
 * Utility functions for handling video URLs and optimization (Azure Blob Storage focused)
 */

import { isAzureBlobStorageUrl, getAzureBlobBaseUrl, hasAzureSasToken } from './image-utils';

/**
 * Supported video formats for different use cases
 */
export const VIDEO_FORMATS = {
  // Modern formats (better compression)
  modern: ['mp4', 'webm', 'av1'],
  // Legacy formats (broader compatibility)
  legacy: ['mp4', 'mov', 'avi'],
  // Streaming formats
  streaming: ['m3u8', 'mpd'],
} as const;

/**
 * Video loading strategies for different scenarios
 */
export const VIDEO_LOADING_CONFIG = {
  // For video galleries/previews
  gallery: {
    preload: 'metadata' as const,
    muted: true,
    autoplay: false,
    controls: true,
    poster: true, // Show poster image
  },
  
  // For hero/featured videos
  hero: {
    preload: 'auto' as const,
    muted: true,
    autoplay: true,
    controls: false,
    poster: false,
  },
  
  // For full video player
  player: {
    preload: 'metadata' as const,
    muted: false,
    autoplay: false,
    controls: true,
    poster: true,
  },
  
  // For background videos
  background: {
    preload: 'auto' as const,
    muted: true,
    autoplay: true,
    controls: false,
    poster: false,
  },
} as const;

export type VideoLoadingType = keyof typeof VIDEO_LOADING_CONFIG;

/**
 * Check if a URL is a video file
 */
export function isVideoUrl(url: string): boolean {
  const videoExtensions = /\.(mp4|webm|ogg|avi|mov|wmv|flv|mkv|m4v|3gp|m3u8|mpd)(\?.*)?$/i;
  return videoExtensions.test(url);
}

/**
 * Get video format from URL
 */
export function getVideoFormat(url: string): string | null {
  const match = url.match(/\.([^.?]+)(\?.*)?$/);
  return match ? match[1].toLowerCase() : null;
}

/**
 * Check if video format is modern (better compression)
 */
export function isModernVideoFormat(url: string): boolean {
  const format = getVideoFormat(url);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return format ? VIDEO_FORMATS.modern.includes(format as any) : false;
}

/**
 * Generate poster image URL from video URL (Azure Blob Storage)
 */
export function generatePosterUrl(videoUrl: string): string | null {
  if (!isAzureBlobStorageUrl(videoUrl)) return null;
  
  // For Azure Blob Storage, try to find a corresponding poster image
  const baseUrl = getAzureBlobBaseUrl(videoUrl);
  const posterUrl = baseUrl.replace(/\.(mp4|webm|ogg|avi|mov|wmv|flv|mkv|m4v|3gp)$/i, '_poster.jpg');
  
  return posterUrl !== baseUrl ? posterUrl : null;
}

/**
 * Get optimal video attributes based on loading type
 */
export function getVideoAttributes(loadingType: VideoLoadingType = 'gallery') {
  return VIDEO_LOADING_CONFIG[loadingType];
}

/**
 * Check if video should be lazy loaded
 */
export function shouldLazyLoadVideo(index: number, isAboveFold: boolean = false): boolean {
  // Don't lazy load first 3 videos or above-fold videos
  return index >= 3 && !isAboveFold;
}

function extractSasToken(url: string): string | undefined {
  if (!hasAzureSasToken(url)) {
    return undefined;
  }

  const [, token] = url.split('?');
  return token || undefined;
}

function buildVideoSourceUrl(
  baseWithoutExt: string,
  format: string,
  sasToken?: string
): string {
  if (!sasToken) {
    return `${baseWithoutExt}.${format}`;
  }
  return `${baseWithoutExt}.${format}?${sasToken}`;
}

/**
 * Generate video source elements for multiple formats
 */
export function generateVideoSources(baseUrl: string): Array<{ src: string; type: string }> {
  if (!isAzureBlobStorageUrl(baseUrl)) {
    return [{ src: baseUrl, type: `video/${getVideoFormat(baseUrl) || 'mp4'}` }];
  }
  
  const sources = [];
  const baseWithoutExt = getAzureBlobBaseUrl(baseUrl).replace(/\.[^.]+$/, '');
  const sasToken = extractSasToken(baseUrl);
  
  // Try modern formats first
  for (const format of VIDEO_FORMATS.modern) {
    const src = buildVideoSourceUrl(baseWithoutExt, format, sasToken);
    sources.push({
      src,
      type: `video/${format === 'av1' ? 'mp4; codecs="av01"' : format}`,
    });
  }
  
  return sources;
}

/**
 * Get video loading priority based on position and type
 */
export function getVideoLoadingPriority(
  index: number, 
  loadingType: VideoLoadingType,
  isAboveFold: boolean = false
): 'high' | 'low' | 'auto' {
  if (loadingType === 'hero' || isAboveFold) return 'high';
  if (index < 3) return 'high';
  return 'auto';
}

/**
 * Calculate optimal video dimensions for responsive design
 */
export function getOptimalVideoDimensions(
  containerWidth: number,
  aspectRatio: number = 16/9
): { width: number; height: number } {
  const width = Math.min(containerWidth, 1920); // Max 1920px width
  const height = Math.round(width / aspectRatio);
  
  return { width, height };
}

/**
 * Video caching configuration for service worker
 */
export const VIDEO_CACHE_CONFIG = {
  // Cache strategy for video metadata
  metadata: {
    strategy: 'stale-while-revalidate',
    maxAge: 24 * 60 * 60, // 24 hours
  },
  
  // Cache strategy for video thumbnails/posters
  thumbnails: {
    strategy: 'cache-first',
    maxAge: 7 * 24 * 60 * 60, // 7 days
  },
  
  // Don't cache actual video files (too large)
  videos: {
    strategy: 'network-only',
  },
} as const;

/**
 * Generate video thumbnail URL for Azure Blob Storage
 */
export function generateThumbnailUrl(
  videoUrl: string, 
  timeOffset: number = 1
): string | null {
  if (!isAzureBlobStorageUrl(videoUrl)) return null;
  
  const baseUrl = getAzureBlobBaseUrl(videoUrl);
  const thumbnailUrl = baseUrl.replace(
    /\.(mp4|webm|ogg|avi|mov|wmv|flv|mkv|m4v|3gp)$/i, 
    `_thumb_${timeOffset}s.jpg`
  );
  
  return thumbnailUrl !== baseUrl ? thumbnailUrl : null;
} 
