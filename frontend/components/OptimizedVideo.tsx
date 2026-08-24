"use client";

import { useState, useRef, forwardRef, useEffect } from 'react';
import { isAzureBlobStorageUrl } from '@/utils/image-utils';
import { 
  generatePosterUrl, 
  getVideoAttributes,
  shouldLazyLoadVideo,
  generateVideoSources,
  type VideoLoadingType 
} from '@/utils/video-utils';

interface OptimizedVideoProps {
  src: string;
  className?: string;
  width?: number;
  height?: number;
  loadingType?: VideoLoadingType;
  index?: number;
  isAboveFold?: boolean;
  onLoad?: () => void;
  onError?: () => void;
  onPlay?: () => void;
  onPause?: () => void;
  poster?: string; // Override poster URL
  muted?: boolean; // Override muted setting
  autoplay?: boolean; // Override autoplay setting
  controls?: boolean; // Override controls setting
}

export const OptimizedVideo = forwardRef<HTMLVideoElement, OptimizedVideoProps>(
  ({ 
    src, 
    className, 
    width, 
    height, 
    loadingType = 'gallery',
    index = 0,
    isAboveFold = false,
    onLoad,
    onError,
    onPlay,
    onPause,
    poster: customPoster,
    muted: customMuted,
    autoplay: customAutoplay,
    controls: customControls,
  }, ref) => {
    const [videoError, setVideoError] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [shouldLoad, setShouldLoad] = useState(!shouldLazyLoadVideo(index, isAboveFold));
    const videoRef = useRef<HTMLVideoElement>(null);
    const lazyLoadTargetRef = useRef<HTMLDivElement>(null);
    const observerRef = useRef<IntersectionObserver | null>(null);

    // Get loading configuration
    const config = getVideoAttributes(loadingType);
    
    // Override config with custom props
    const finalMuted = customMuted !== undefined ? customMuted : config.muted;
    const finalAutoplay = customAutoplay !== undefined ? customAutoplay : config.autoplay;
    const finalControls = customControls !== undefined ? customControls : config.controls;
    
    // Generate poster URL if not provided and config requires it
    const posterUrl = customPoster ??
      (config.poster && isAzureBlobStorageUrl(src)
        ? generatePosterUrl(src) ?? undefined
        : undefined);
    
    // Generate video sources for Azure Blob Storage
    const videoSources = isAzureBlobStorageUrl(src) ? generateVideoSources(src) : [{ src, type: 'video/mp4' }];

    // Set up intersection observer for lazy loading
    useEffect(() => {
      const target = lazyLoadTargetRef.current;
      if (shouldLoad || !target) return;

      observerRef.current = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              setShouldLoad(true);
              observerRef.current?.disconnect();
            }
          });
        },
        { 
          rootMargin: '50px', // Start loading 50px before entering viewport
          threshold: 0.1 
        }
      );

      observerRef.current.observe(target);

      return () => {
        observerRef.current?.disconnect();
      };
    }, [shouldLoad]);

    // Handle video events
    const handleLoadStart = () => {
      setIsLoading(true);
    };

    const handleCanPlay = () => {
      setIsLoading(false);
      setVideoError(false);
      onLoad?.();
    };

    const handleError = () => {
      setVideoError(true);
      setIsLoading(false);
      onError?.();
    };

    const handlePlay = () => {
      onPlay?.();
    };

    const handlePause = () => {
      onPause?.();
    };

    // Don't render video sources until we should load
    if (!shouldLoad) {
      return (
        <div 
          ref={lazyLoadTargetRef}
          className={`bg-gray-200 dark:bg-gray-800 flex items-center justify-center ${className}`}
          style={{ width, height }}
        >
          <div className="text-gray-500 text-sm">Loading video...</div>
        </div>
      );
    }

    // Show error state
    if (videoError) {
      return (
        <div 
          className={`bg-gray-100 dark:bg-gray-900 flex items-center justify-center border-2 border-dashed border-gray-300 dark:border-gray-700 ${className}`}
          style={{ width, height }}
        >
          <div className="text-center text-gray-500">
            <div className="text-sm">Video unavailable</div>
            <div className="text-xs mt-1">Failed to load video</div>
          </div>
        </div>
      );
    }

    return (
      <video
        ref={(node) => {
          if (typeof ref === 'function') {
            ref(node);
          } else if (ref) {
            ref.current = node;
          }
          if (videoRef.current !== node) {
            videoRef.current = node;
          }
        }}
        className={className}
        width={width}
        height={height}
        poster={posterUrl}
        muted={finalMuted}
        autoPlay={finalAutoplay}
        controls={finalControls}
        preload={config.preload}
        playsInline
        onLoadStart={handleLoadStart}
        onCanPlay={handleCanPlay}
        onError={handleError}
        onPlay={handlePlay}
        onPause={handlePause}
        style={{
          opacity: isLoading ? 0.7 : 1,
          transition: 'opacity 0.3s ease',
        }}
      >
        {videoSources.map((source, idx) => (
          <source key={idx} src={source.src} type={source.type} />
        ))}
        <div className="bg-gray-100 dark:bg-gray-900 flex items-center justify-center p-4">
          <p className="text-gray-600 dark:text-gray-400">
            Your browser does not support the video tag.
          </p>
        </div>
      </video>
    );
  }
);

OptimizedVideo.displayName = 'OptimizedVideo';
