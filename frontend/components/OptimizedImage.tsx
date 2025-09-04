"use client";

import Image from 'next/image';
import { useState, forwardRef } from 'react';
import { isExternalImageUrl, getFallbackImageUrl, type ImageLoadingType, IMAGE_LOADING_CONFIG } from '@/utils/image-utils';

interface OptimizedImageProps {
  src: string;
  alt: string;
  fill?: boolean;
  sizes?: string;
  className?: string;
  onLoad?: () => void;
  onError?: () => void;
  priority?: boolean;
  width?: number;
  height?: number;
  loadingType?: ImageLoadingType;
  quality?: number;
}

// Custom image component that handles external URLs gracefully
export const OptimizedImage = forwardRef<HTMLImageElement, OptimizedImageProps>(
  ({ 
    src, 
    alt, 
    fill, 
    sizes, 
    className, 
    onLoad, 
    onError, 
    priority, 
    width, 
    height, 
    loadingType = 'gallery',
    quality 
  }, ref) => {
    const [imageError, setImageError] = useState(false);
    const [fallbackUsed, setFallbackUsed] = useState(false);
    
    // Get loading configuration
    const loadingConfig = IMAGE_LOADING_CONFIG[loadingType];
    const finalSizes = sizes || loadingConfig.sizes;
    const finalPriority = priority !== undefined ? priority : loadingConfig.priority;
    const finalQuality = quality || loadingConfig.quality;
    
    // Check if the image is from an external source or has SAS tokens
    const isExternal = isExternalImageUrl(src);
    const hasSasToken = src.includes('?sv=') || src.includes('?sig=');
    
    // Handle image error
    const handleError = () => {
      if (!fallbackUsed) {
        setImageError(true);
        setFallbackUsed(true);
      }
      onError?.();
    };
    
    // Handle image load
    const handleLoad = () => {
      setImageError(false);
      onLoad?.();
    };
    
    // Use fallback image if there was an error
    const imageSrc = imageError && fallbackUsed 
      ? getFallbackImageUrl(width || 400, height || 300)
      : src;
    
    // If it's an external image or has SAS tokens, use unoptimized
    if (isExternal || hasSasToken) {
      const safeWidth = !fill ? (width || 1024) : undefined;
      const safeHeight = !fill ? (height || 1024) : undefined;
      
      return (
        <Image
          ref={ref}
          src={imageSrc}
          alt={alt}
          fill={fill}
          width={safeWidth}
          height={safeHeight}
          sizes={finalSizes}
          className={className}
          onLoad={handleLoad}
          onError={handleError}
          priority={finalPriority}
          quality={finalQuality}
          unoptimized
        />
      );
    }
    
    // For internal images without SAS tokens, use optimized version
    const safeWidth = !fill ? (width || 1024) : undefined;
    const safeHeight = !fill ? (height || 1024) : undefined;
    
    return (
      <Image
        ref={ref}
        src={imageSrc}
        alt={alt}
        fill={fill}
        width={safeWidth}
        height={safeHeight}
        sizes={finalSizes}
        className={className}
        onLoad={handleLoad}
        onError={handleError}
        priority={finalPriority}
        quality={finalQuality}
      />
    );
  }
);

OptimizedImage.displayName = 'OptimizedImage'; 