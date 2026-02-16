"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { PageHeader } from "@/components/page-header";
import { Loader2, RefreshCw, Clock, ImageIcon } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatDistanceToNow } from "date-fns";
import { fetchImages, ImageMetadata as GalleryImageMetadata } from "@/utils/gallery-utils";
import { ImageGalleryCard } from "@/components/image-gallery-card";
import { ImageCreationContainer } from "@/components/ImageCreationContainer";
import { Badge } from "@/components/ui/badge";
import { useSearchParams } from "next/navigation";
import { FolderIcon } from "lucide-react";
import { PageTransition } from "@/components/ui/page-transition";
import { ImageDetailView } from "@/components/ImageDetailView";
import { RowBasedMasonryGrid } from "@/components/RowBasedMasonryGrid";

// For the 'any' type issue, let's define a proper interface
interface GalleryImageItem {
  src: string;
  id: string;
  name: string;
  metadata?: {
    tags?: string;
    description?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

interface ImageMetadata {
  src: string;
  title: string;
  description?: string;
  id: string;
  name: string;
  tags?: string[];
  originalItem: GalleryImageItem;
  width?: number;
  height?: number;
  size?: "small" | "medium" | "large";
}

// Separate component that uses useSearchParams
function NewImagePageContent() {
  const searchParams = useSearchParams();
  const folderPath = searchParams.get('folder');
  
  const [images, setImages] = useState<ImageMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [lastRefreshedText, setLastRefreshedText] = useState<string>("Never refreshed");
  const [fullscreenImage, setFullscreenImage] = useState<ImageMetadata | null>(null);

  const limit = 50;

  // Log changes to fullscreenImage dimensions
  useEffect(() => {
    if (fullscreenImage) {
      console.log("FullscreenImage updated:", {
        id: fullscreenImage.id,
        width: fullscreenImage.width,
        height: fullscreenImage.height
      });
    }
  }, [fullscreenImage]);

  const loadImages = useCallback(async (resetImages = true, isAutoRefresh = false) => {
    if (resetImages) {
      if (!isAutoRefresh) {
        setLoading(true);
      } else {
        setIsRefreshing(true);
      }
      setOffset(0);
    } else {
      setIsLoadingMore(true);
    }

    try {
      // Fetch images - they will be sorted by creation time (newest first) in the fetchImages function
      const fetchedImagesRaw = await fetchImages(limit, resetImages ? 0 : offset, folderPath || undefined);
      
      // Convert GalleryImageMetadata to our local ImageMetadata type
      const fetchedImages = fetchedImagesRaw.map((image: GalleryImageMetadata): ImageMetadata => ({
        src: image.src,
        title: image.title,
        description: image.description,
        id: image.id,
        name: image.name,
        tags: image.tags,
        originalItem: {
          src: image.src,
          id: image.id,
          name: image.name,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          metadata: image.originalItem.metadata as any
        },
        width: image.width,
        height: image.height,
        size: image.size,
        analysis: image.analysis
      }));
      
      if (resetImages) {
        setImages(fetchedImages);
        
        // Update last refreshed time
        const now = new Date();
        setLastRefreshed(now);
        setLastRefreshedText(`Last refreshed ${formatDistanceToNow(now, { addSuffix: true })}`);
      } else {
        setImages(prevImages => [...prevImages, ...fetchedImages]);
      }
      
      // If we got fewer images than the limit, there are no more images to load
      setHasMore(fetchedImages.length >= limit);
      
      // Update offset for next page
      if (!resetImages) {
        setOffset(prevOffset => prevOffset + limit);
      }
    } catch (error) {
      console.error("Failed to load images:", error);
      toast.error("Error loading images", {
        description: "Failed to load images from the gallery"
      });
    } finally {
      setLoading(false);
      setIsLoadingMore(false);
      setIsRefreshing(false);
    }
  }, [limit, offset, folderPath]);

  // Toggle auto-refresh
  const toggleAutoRefresh = () => {
    setAutoRefresh(prev => !prev);
  };

  // Create a separate auto-refresh function to avoid dependency issues
  const autoRefreshImages = useCallback(async () => {
    try {
      setIsRefreshing(true);
      
      // Fetch fresh images
      const fetchedImages = await fetchImages(limit, 0, folderPath || undefined);
      
      // Map to the expected format
      const mappedImages: ImageMetadata[] = fetchedImages.map(image => ({
        src: image.src,
        title: image.title,
        description: image.description,
        id: image.id,
        name: image.name,
        tags: image.tags,
        originalItem: {
          src: image.src,
          id: image.id,
          name: image.name,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          metadata: image.originalItem.metadata as any
        },
        width: image.width,
        height: image.height,
        size: image.size
      }));
      
      setImages(mappedImages);
      setOffset(0);
      setHasMore(mappedImages.length >= limit);
      
      // Update last refreshed time
      const now = new Date();
      setLastRefreshed(now);
      setLastRefreshedText(`Last refreshed ${formatDistanceToNow(now, { addSuffix: true })}`);
      
    } catch (error) {
      console.error("Auto-refresh failed:", error);
    } finally {
      setIsRefreshing(false);
    }
  }, [limit, folderPath]);

  // Handle auto refresh toggle
  useEffect(() => {
    if (autoRefresh) {
      // Set up a refresh interval (every 30 seconds)
      const interval = setInterval(() => {
        autoRefreshImages();
      }, 30000); // 30 seconds
      
      setRefreshInterval(interval);
      
      // Cleanup interval on component unmount or when autoRefresh is turned off
      return () => {
        clearInterval(interval);
        setRefreshInterval(null);
      };
    } else if (refreshInterval) {
      // Clear the interval if auto refresh is turned off
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
  }, [autoRefresh, autoRefreshImages, refreshInterval]); // Only depend on autoRefresh and the stable autoRefreshImages function

  // Update the "time ago" text every minute
  useEffect(() => {
    if (!lastRefreshed) return;
    
    const updateLastRefreshedText = () => {
      if (lastRefreshed) {
        setLastRefreshedText(`Last refreshed ${formatDistanceToNow(lastRefreshed, { addSuffix: true })}`);
      }
    };
    
    // Update immediately
    updateLastRefreshedText();
    
    // Then update every minute
    const interval = setInterval(updateLastRefreshedText, 60000);
    
    return () => clearInterval(interval);
  }, [lastRefreshed]);

  // Reset images and reload when folder path changes
  useEffect(() => {
    setOffset(0);
    setImages([]);
    loadImages(true);
  }, [folderPath, loadImages]);

  // Function to load more images
  const loadMoreImages = () => {
    if (!hasMore || isLoadingMore) return;
    loadImages(false);
  };

  // Generate skeleton placeholders for loading state
  const renderSkeletons = (count: number) => {
    return Array.from({ length: count }).map((_, index) => (
      <Card 
        key={`skeleton-${index}`}
        className="overflow-hidden border-0 rounded-xl h-full w-full"
      >
        <AspectRatio ratio={
          index % 5 === 0 
            ? 16/9  // Landscape ratio for large items
            : index % 3 === 0 
              ? 3/4  // Portrait ratio for tall items
              : 4/3  // Standard ratio for medium items
        } className="bg-muted">
          <Skeleton className="h-full w-full rounded-none" />
        </AspectRatio>
        <div className="p-3 space-y-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </Card>
    ));
  };

  // Function to handle image click - Opens the full-screen modal
  const handleImageClick = (image: ImageMetadata) => {
    // Create a copy of the image for state update
    const updatedImage = { ...image };
    
    // Try to get image dimensions if not already available
    if (!updatedImage.width || !updatedImage.height) {
      // Create a temporary image to get dimensions
      const tempImg = new window.Image();
      
      // Add crossOrigin attribute to prevent CORS issues
      tempImg.crossOrigin = "anonymous";
      
      // Set up load event to capture dimensions
      tempImg.onload = () => {
        updatedImage.width = tempImg.width;
        updatedImage.height = tempImg.height;
        console.log("Image loaded with dimensions:", tempImg.width, "x", tempImg.height);
        setFullscreenImage(updatedImage);
      };
      
      // Add timestamp to URL to prevent caching issues
      const cacheBuster = `${image.src.includes('?') ? '&' : '?'}_t=${Date.now()}`;
      
      // Use the normal image src for all cases (now using SAS tokens)
      tempImg.src = image.src + cacheBuster;
    }
    
    // Find the index of the clicked image
    const imageIndex = images.findIndex(img => img.id === image.id);
    console.log("Image index:", imageIndex);
    
    setFullscreenImage(updatedImage);
    
    // Check if the image already has analysis data in its metadata
    if (updatedImage.originalItem?.metadata) {
      try {
        const metadata = updatedImage.originalItem.metadata;
        
        // Check if the image has analysis data - either by the analyzed flag or by checking for description/tags
        if (metadata.analyzed === "true" || metadata.description || metadata.tags) {
          // For tags, try to parse them if they exist and are stored as a string
          let parsedTags: string[] = [];
          
          if (metadata.tags) {
            try {
              // Check if it's already a string array or needs parsing from JSON
              if (typeof metadata.tags === 'string') {
                parsedTags = JSON.parse(metadata.tags);
              }
            } catch (e) {
              console.warn("Failed to parse tags:", e);
            }
          }
          
          // Analysis data was previously set here
          console.log("Found analysis data in metadata:", {
            description: metadata.description,
            tags: parsedTags,
            products: metadata.products,
            feedback: metadata.feedback
          });
        }
      } catch (e) {
        console.warn("Error extracting analysis data from metadata:", e);
      }
    }
  };

  // Wrap navigateImage in useCallback to fix the exhaustive-deps warning
  const navigateImage = useCallback((direction: 'prev' | 'next') => {
    if (!fullscreenImage || !images.length) return;
    
    // Find current index
    const currentIndex = images.findIndex(img => img.id === fullscreenImage.id);
    
    // Exit if not found
    if (currentIndex === -1) return;
    
    // Calculate new index
    let newIndex = currentIndex;
    if (direction === 'prev') {
      newIndex = currentIndex === 0 ? images.length - 1 : currentIndex - 1;
    } else {
      newIndex = currentIndex === images.length - 1 ? 0 : currentIndex + 1;
    }
    
    // Update fullscreen image
    setFullscreenImage(images[newIndex]);
  }, [fullscreenImage, images]);





  // Keyboard navigation for fullscreen viewer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!fullscreenImage) return;
      
      if (e.key === 'ArrowLeft') {
        navigateImage('prev');
      } else if (e.key === 'ArrowRight') {
        navigateImage('next');
      } else if (e.key === 'Escape') {
        setFullscreenImage(null);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [fullscreenImage, images, navigateImage]);


  


  // Function to load only the newest images and update the gallery
  const loadNewImages = useCallback(async (count: number = 5) => {
    // Let's just do a complete reload but with better UX - loading in the background
    const tempLoading = isRefreshing;
    setIsRefreshing(true);
    
    try {
      // Remember current scroll position
      const galleryContainer = document.querySelector('.gallery-container');
      const scrollPosition = galleryContainer?.scrollTop || 0;
      
      console.log(`Reloading gallery after generating ${count} new images`);
      
      // Simply get the updated list of images
      const fetchedImages = await fetchImages(limit, 0, folderPath || undefined);
      
      if (fetchedImages.length > 0) {
        // Instead of trying to compare and merge, just set the new images
        setImages(fetchedImages);
        
        // Update last refreshed time
        const now = new Date();
        setLastRefreshed(now);
        setLastRefreshedText(`Last refreshed ${formatDistanceToNow(now, { addSuffix: true })}`);
        
        // Toast notification
        toast.success(`Gallery updated with ${count} new image${count > 1 ? 's' : ''}`, {
          description: "New images have been added to the gallery"
        });
        
        // Restore scroll position after a short delay to ensure rendering is complete
        setTimeout(() => {
          if (galleryContainer) {
            galleryContainer.scrollTop = scrollPosition;
          }
        }, 100);
      }
    } catch (error) {
      console.error("Failed to reload gallery with new images:", error);
      toast.error("Error updating gallery", {
        description: "Failed to load newly generated images"
      });
    } finally {
      setIsRefreshing(tempLoading);
    }
  }, [limit, folderPath, isRefreshing]);



  return (
    <div className="flex flex-col h-full w-full">
      <PageHeader 
        title={folderPath ? "Album" : "All Images"} 
      />
      
      <div className="flex-1 w-full h-full overflow-y-auto gallery-container">
        <div className="w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-32">
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <div className="text-xs text-muted-foreground">
                {lastRefreshedText}
              </div>
              {folderPath && (
                <Badge variant="outline" className="ml-2">
                  <FolderIcon className="h-3 w-3 mr-1" />
                  {folderPath.split('/').pop() || folderPath}
                </Badge>
              )}
            </div>
            
            <div className="flex items-center space-x-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="icon"
                      variant={autoRefresh ? "outline" : "ghost"}
                      className={`relative h-8 w-8 ${autoRefresh ? 'border-primary text-primary' : 'text-muted-foreground'}`}
                      onClick={toggleAutoRefresh}
                    >
                      <Clock className="h-4 w-4" />
                      {autoRefresh && (
                        <span className="absolute bottom-1 right-1 h-1.5 w-1.5 rounded-full bg-primary" />
                      )}
                      <span className="sr-only">
                        {autoRefresh ? 'Disable auto-refresh' : 'Enable auto-refresh'}
                      </span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="left">
                    {autoRefresh ? 'Auto-refresh every 30s (on)' : 'Auto-refresh every 30s (off)'}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <Button 
                variant="outline" 
                size="icon" 
                onClick={() => loadImages(true)}
                disabled={loading || isRefreshing}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span className="sr-only">Refresh gallery</span>
              </Button>
            </div>
          </div>
          
          {loading ? (
            <RowBasedMasonryGrid columns={3} gap={4}>
              {renderSkeletons(16)}
            </RowBasedMasonryGrid>
          ) : images.length > 0 ? (
            <div className="w-full">
              {/* Row-based masonry grid for left-to-right, top-to-bottom ordering */}
              <RowBasedMasonryGrid columns={3} gap={4}>
                {images.map((image, index) => (
                  <ImageGalleryCard
                    key={image.name}
                    image={image}
                    index={index}
                    onClick={() => handleImageClick(image)}
                    onDelete={(deletedImageId) => {
                      // Remove the deleted image from the state
                      setImages(prevImages => prevImages.filter(img => img.id !== deletedImageId));
                      
                      // If we've deleted an image, we might want to load another one to replace it
                      if (hasMore && images.length < limit * 2) {
                        loadMoreImages();
                      }
                    }}
                    onMove={(movedImageId) => {
                      // Only remove the moved image if we're in a folder view
                      if (folderPath) {
                        // Remove the moved image from the current state
                        setImages(prevImages => prevImages.filter(img => img.id !== movedImageId));
                        
                        // If we've moved an image, we might want to load another one to replace it
                        if (hasMore && images.length < limit * 2) {
                          loadMoreImages();
                        }
                      } else {
                        // When in "All Images" view, refresh the gallery to update
                        loadImages(true);
                      }
                      
                      toast.success("Image moved", {
                        description: "The image was moved to another folder"
                      });
                    }}
                  />
                ))}
              </RowBasedMasonryGrid>
              
              {/* Load more button */}
              {hasMore && (
                <div className="mt-8 flex justify-center">
                  <Button
                    onClick={loadMoreImages}
                    disabled={isLoadingMore}
                    variant="outline"
                    className="px-8"
                  >
                    {isLoadingMore ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Loading...
                      </>
                    ) : (
                      'Load More Images'
                    )}
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-[calc(100vh-14rem)] py-20 text-muted-foreground">
              <ImageIcon className="h-16 w-16 mb-4 opacity-20" />
              {folderPath ? (
                <>
                  <p className="text-xl">This album is empty</p>
                  <p className="text-sm mt-2">No images found in album &quot;{folderPath.split('/').pop() || folderPath}&quot;</p>
                </>
              ) : (
                <>
                  <p className="text-xl">No images found in the gallery</p>
                  <p className="text-sm mt-2">Upload some images to get started</p>
                </>
              )}
              <Button 
                onClick={() => loadImages(true)} 
                variant="outline" 
                className="mt-6"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh Gallery
              </Button>
            </div>
          )}
        </div>
        
        {/* Image Creation Container - sticky positioned at the bottom */}
        <div className="sticky bottom-0 w-full">
          <ImageCreationContainer 
            onImagesSaved={(count) => loadNewImages(count || 5)} 
          />
        </div>
      </div>
      
      {/* Full-screen Image Viewer Modal */}
      {fullscreenImage && (
        <ImageDetailView
          image={fullscreenImage}
          images={images}
          onClose={() => setFullscreenImage(null)}
          onDelete={(imageId) => {
            // Remove the deleted image from the state
            setImages(prevImages => prevImages.filter(img => img.id !== imageId));
            // If in a folder view, load more images if needed
            if (folderPath && hasMore && images.length < limit * 2) {
              loadMoreImages();
            }
          }}
          onMove={(imageId) => {
            // Only remove the moved image if we're in a folder view
            if (folderPath) {
              // Remove the moved image from the current state
              setImages(prevImages => prevImages.filter(img => img.id !== imageId));
              
              // If we've moved an image, we might want to load another one to replace it
              if (hasMore && images.length < limit * 2) {
                loadMoreImages();
              }
            } else {
              // When in "All Images" view, refresh the gallery to update
              loadImages(true);
            }
          }}
          onNavigate={(direction, newIndex) => {
            setFullscreenImage(images[newIndex]);
          }}
        />
      )}
    </div>
  );
}

export default function NewImagePage() {
  return (
    <PageTransition>
      <Suspense fallback={<div>Loading...</div>}>
      <NewImagePageContent />
    </Suspense>
    </PageTransition>
  );
} 