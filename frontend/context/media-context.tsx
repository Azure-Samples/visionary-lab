"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface MediaContextType {
  screenWidth: number;
  screenHeight: number;
  isHighBandwidth: boolean;
  prefersReducedData: boolean;
  devicePixelRatio: number;
  connectionType: string;
  effectiveConnectionType: string;
}

// Interface for Navigator with connection property
interface NavigatorWithConnection extends Navigator {
  connection?: {
    downlink: number;
    effectiveType: string;
    saveData: boolean;
    type: string;
    addEventListener: (event: string, listener: () => void) => void;
    removeEventListener: (event: string, listener: () => void) => void;
  };
}

const defaultMediaContext: MediaContextType = {
  screenWidth: typeof window !== 'undefined' ? window.innerWidth : 1920,
  screenHeight: typeof window !== 'undefined' ? window.innerHeight : 1080,
  isHighBandwidth: true,
  prefersReducedData: false,
  devicePixelRatio: typeof window !== 'undefined' ? window.devicePixelRatio : 1,
  connectionType: 'unknown',
  effectiveConnectionType: '4g',
};

const MediaContext = createContext<MediaContextType>(defaultMediaContext);

export function MediaProvider({ children }: { children: ReactNode }) {
  const [mediaContext, setMediaContext] = useState<MediaContextType>(defaultMediaContext);

  useEffect(() => {
    // Handle window resize
    const handleResize = () => {
      setMediaContext(prev => ({
        ...prev,
        screenWidth: window.innerWidth,
        screenHeight: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio
      }));
    };
    
    // Check network conditions
    const updateConnectionInfo = () => {
      const navigatorWithConnection = navigator as NavigatorWithConnection;
      if (navigatorWithConnection.connection) {
        const connection = navigatorWithConnection.connection;
        
        setMediaContext(prev => ({
          ...prev,
          isHighBandwidth: connection.downlink >= 1.5 && 
                           !connection.saveData && 
                           (connection.effectiveType === '4g'),
          prefersReducedData: connection.saveData,
          connectionType: connection.type || 'unknown',
          effectiveConnectionType: connection.effectiveType || '4g'
        }));
      }
    };
    
    // Add event listeners
    window.addEventListener('resize', handleResize, { passive: true });
    const navigatorWithConnection = navigator as NavigatorWithConnection;
    if (navigatorWithConnection.connection) {
      navigatorWithConnection.connection.addEventListener('change', updateConnectionInfo);
    }
    
    // Initial check
    updateConnectionInfo();
    
    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      const navigatorWithConnection = navigator as NavigatorWithConnection;
      if (navigatorWithConnection.connection) {
        navigatorWithConnection.connection.removeEventListener('change', updateConnectionInfo);
      }
    };
  }, []);
  
  return (
    <MediaContext.Provider value={mediaContext}>
      {children}
    </MediaContext.Provider>
  );
}

// Custom hook to use the media context
export const useMedia = () => useContext(MediaContext);

// Helper function to determine if the client should load high-quality media
export const shouldLoadHighQuality = (mediaContext: MediaContextType): boolean => {
  return mediaContext.isHighBandwidth && !mediaContext.prefersReducedData;
};

// Helper function to determine optimal image size based on screen width
export const getOptimalImageSize = (
  mediaContext: MediaContextType,
  originalWidth?: number,
  originalHeight?: number
): { width: number, height: number } => {
  const { screenWidth, devicePixelRatio, isHighBandwidth } = mediaContext;
  
  // Default to a reasonable size if original dimensions are unknown
  if (!originalWidth || !originalHeight) {
    // For high bandwidth, use higher resolution
    if (isHighBandwidth) {
      return { 
        width: Math.min(1200, screenWidth * devicePixelRatio),
        height: Math.min(1200, screenWidth * devicePixelRatio)
      };
    }
    
    // For low bandwidth, use lower resolution
    return {
      width: Math.min(800, screenWidth),
      height: Math.min(800, screenWidth)
    };
  }
  
  // Calculate aspect ratio
  const aspectRatio = originalWidth / originalHeight;
  
  // Determine target width based on screen size and device pixel ratio
  let targetWidth = screenWidth;
  
  // For small screens, use full screen width
  // For medium screens, use 70% of screen width
  // For large screens, use 50% of screen width
  if (screenWidth > 1200) {
    targetWidth = screenWidth * 0.5;
  } else if (screenWidth > 768) {
    targetWidth = screenWidth * 0.7;
  }
  
  // Adjust for device pixel ratio for high-quality displays
  if (isHighBandwidth) {
    targetWidth = targetWidth * devicePixelRatio;
  }
  
  // Cap at original width
  targetWidth = Math.min(targetWidth, originalWidth);
  
  // Calculate height maintaining aspect ratio
  const targetHeight = targetWidth / aspectRatio;
  
  return { 
    width: Math.round(targetWidth),
    height: Math.round(targetHeight)
  };
}; 