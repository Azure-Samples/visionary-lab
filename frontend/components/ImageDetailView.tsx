"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { 
  X, ChevronLeft, ChevronRight, Download, Trash2, FolderUp, Loader2, Maximize, Minimize, Info 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MediaType, deleteGalleryAsset, fetchFolders, moveAsset } from "@/services/api";
import { OptimizedImage } from "@/components/OptimizedImage";

interface ImageMetadata {
  src: string;
  title: string;
  description?: string;
  id: string;
  name: string;
  tags?: string[];
  originalItem: {
    metadata?: {
      prompt?: string;
      description?: string;
      has_transparency?: string;
      width?: string;
      height?: string;
      createdAt?: string;
      [key: string]: string | number | boolean | undefined;
    };
    size?: number;
    url?: string;
    [key: string]: string | number | boolean | object | undefined;
  };
  width?: number;
  height?: number;
  analysis?: {
    summary?: string;
    products?: string;
    feedback?: string;
    tags?: string[];
    analyzed?: boolean;
  };
}

interface ImageDetailViewProps {
  image: ImageMetadata | null;
  images: ImageMetadata[];
  onClose: () => void;
  onDelete: (imageId: string) => void;
  onMove?: (imageId: string) => void;
  onNavigate?: (direction: 'prev' | 'next', index: number) => void;
}

export function ImageDetailView({ 
  image, 
  images, 
  onClose, 
  onDelete,
  onMove,
  onNavigate
}: ImageDetailViewProps) {
  // Refs
  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // State
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isMoving, setIsMoving] = useState(false);
  const [isError, setIsError] = useState(false);
  const [folders, setFolders] = useState<string[]>([]);
  const [isFoldersLoading, setIsFoldersLoading] = useState(false);
  const [imageStats, setImageStats] = useState<{
    naturalWidth: number;
    naturalHeight: number;
    aspectRatio: number;
    fileSize: string;
  } | null>(null);

  // Load folders when dropdown is opened
  const loadFolders = async () => {
    if (folders.length > 0) return;
    
    try {
      setIsFoldersLoading(true);
      const result = await fetchFolders(MediaType.IMAGE);
      setFolders(result.folders);
    } catch (error) {
      console.error("Failed to fetch folders:", error);
      toast.error("Failed to load folders");
    } finally {
      setIsFoldersLoading(false);
    }
  };

  // Toggle fullscreen
  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(error => {
        console.error("Failed to enter fullscreen:", error);
      });
    } else {
      document.exitFullscreen();
    }
  };

  // Handle fullscreen change
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  // Navigate to another image
  const navigateImage = useCallback((direction: 'prev' | 'next') => {
    if (!image || images.length <= 1) return;
    
    const currentIndex = images.findIndex(img => img.id === image.id);
    if (currentIndex === -1) return;
    
    let newIndex: number;
    if (direction === 'prev') {
      newIndex = currentIndex === 0 ? images.length - 1 : currentIndex - 1;
    } else {
      newIndex = currentIndex === images.length - 1 ? 0 : currentIndex + 1;
    }
    
    // The parent component that owns the ImageDetailView should handle the navigation
    if (onNavigate) {
      onNavigate(direction, newIndex);
    }
  }, [image, images, onNavigate]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          // Only handle Escape if we're not in fullscreen
          if (!document.fullscreenElement) {
            onClose();
          }
          break;
        case 'ArrowLeft':
          if (image && images.length > 1) {
            navigateImage('prev');
          }
          break;
        case 'ArrowRight':
          if (image && images.length > 1) {
            navigateImage('next');
          }
          break;
        case 'f':
          // 'F' to toggle fullscreen
          toggleFullscreen();
          break;
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [image, images, navigateImage, onClose]);

  // Handle image loading and statistics
  useEffect(() => {
    if (image && imageRef.current) {
      const img = imageRef.current;
      
      const handleImageLoad = () => {
        setIsLoading(false);
        setIsError(false);
        
        // Get image dimensions
        const naturalWidth = img.naturalWidth;
        const naturalHeight = img.naturalHeight;
        const aspectRatio = naturalWidth / naturalHeight;
        
        // Set image stats
        setImageStats({
          naturalWidth,
          naturalHeight,
          aspectRatio,
          fileSize: formatFileSize(image.originalItem?.size),
        });
      };
      
      const handleImageError = () => {
        setIsLoading(false);
        setIsError(true);
        setImageStats(null);
      };
      
      // Add event listeners
      img.addEventListener('load', handleImageLoad);
      img.addEventListener('error', handleImageError);
      
      // Check if image is already loaded
      if (img.complete) {
        handleImageLoad();
      }
      
      return () => {
        img.removeEventListener('load', handleImageLoad);
        img.removeEventListener('error', handleImageError);
      };
    }
  }, [image]);

  // Format file size
  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'Unknown';
    
    const kilobyte = 1024;
    const megabyte = kilobyte * 1024;
    
    if (bytes < kilobyte) {
      return `${bytes} B`;
    } else if (bytes < megabyte) {
      return `${(bytes / kilobyte).toFixed(1)} KB`;
    } else {
      return `${(bytes / megabyte).toFixed(1)} MB`;
    }
  };

  // Handle image deletion
  const handleDelete = async () => {
    if (!image || !image.name) {
      toast.error("Cannot delete image", {
        description: "Missing image information"
      });
      return;
    }

    try {
      setIsDeleting(true);
      const result = await deleteGalleryAsset(image.name, MediaType.IMAGE);
      
      if (result.success) {
        toast.success("Image deleted", {
          description: "The image was successfully deleted"
        });
        
        // Notify parent component
        onDelete(image.id);
        
        // Close the detail view
        onClose();
      } else {
        throw new Error(result.message || "Failed to delete image");
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      toast.error("Error deleting image", {
        description: errorMessage
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Handle downloading the image
  const handleDownload = () => {
    if (!image || !image.src) {
      toast.error("Cannot download image", {
        description: "Missing image source"
      });
      return;
    }

    try {
      const a = document.createElement('a');
      a.href = image.src;
      a.download = image.name || 'image-download.png';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      toast.success("Image download started", {
        description: "Your image is being downloaded"
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      toast.error("Error downloading image", {
        description: errorMessage
      });
    }
  };

  // Handle moving the image to a folder
  const handleMove = async (folderPath: string) => {
    if (!image || !image.name) {
      toast.error("Cannot move image", {
        description: "Missing image information"
      });
      return;
    }

    try {
      setIsMoving(true);
      const result = await moveAsset(image.name, folderPath, MediaType.IMAGE);
      
      if (result.success) {
        toast.success("Image moved", {
          description: `The image was successfully moved to "${folderPath}"`
        });
        
        // Notify parent component if provided
        if (onMove) {
          onMove(image.id);
        }
        
        // Close the detail view
        onClose();
      } else {
        throw new Error(result.message || "Failed to move image");
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      toast.error("Error moving image", {
        description: errorMessage
      });
    } finally {
      setIsMoving(false);
    }
  };

  // If no image is provided, don't render anything
  if (!image) return null;

  return (
    <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center overflow-hidden">
      <div 
        ref={containerRef}
        className="bg-background w-full max-w-[90vw] max-h-[90vh] rounded-xl shadow-md flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 bg-background z-10">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigateImage('prev')}
              className="h-8 w-8"
              disabled={images.length <= 1 || isLoading}
            >
              <ChevronLeft className="h-5 w-5" />
              <span className="sr-only">Previous image</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigateImage('next')}
              className="h-8 w-8"
              disabled={images.length <= 1 || isLoading}
            >
              <ChevronRight className="h-5 w-5" />
              <span className="sr-only">Next image</span>
            </Button>
            {isLoading && (
              <div className="ml-2 flex items-center">
                <Loader2 className="h-4 w-4 mr-2 animate-spin text-primary" />
                <span className="text-xs text-muted-foreground">Loading image...</span>
              </div>
            )}
          </div>
          
          {/* Display title in the header */}
          {image && (
            <div className="hidden md:block max-w-lg overflow-hidden text-ellipsis whitespace-nowrap">
              <h2 className="text-lg font-medium">{image.title || 'Untitled Image'}</h2>
              {image.description && (
                <p className="text-xs text-muted-foreground truncate">{image.description}</p>
              )}
            </div>
          )}
          
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDownload}
              className="h-8 w-8"
              disabled={isLoading}
            >
              <Download className="h-4 w-4" />
              <span className="sr-only">Download</span>
            </Button>
            
            <DropdownMenu onOpenChange={(open) => open && loadFolders()}>
              <DropdownMenuTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon"
                  className="h-8 w-8"
                  disabled={isMoving || isLoading}
                >
                  {isMoving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FolderUp className="h-4 w-4" />
                  )}
                  <span className="sr-only">Move to folder</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {isFoldersLoading ? (
                  <DropdownMenuItem disabled>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Loading folders...
                  </DropdownMenuItem>
                ) : folders.length > 0 ? (
                  folders.map((folder) => (
                    <DropdownMenuItem
                      key={folder}
                      onClick={() => handleMove(folder)}
                    >
                      {folder || "Root"}
                    </DropdownMenuItem>
                  ))
                ) : (
                  <DropdownMenuItem disabled>
                    No folders available
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            
            <Button 
              variant="ghost" 
              size="icon"
              className="h-8 w-8 text-destructive hover:bg-destructive/10"
              onClick={handleDelete}
              disabled={isDeleting || isLoading}
            >
              {isDeleting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              <span className="sr-only">Delete</span>
            </Button>
            
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={onClose}
              className="h-8 w-8"
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Close</span>
            </Button>
          </div>
        </div>
        
        {/* Image Viewer */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          <div className="w-full md:w-2/3 flex-shrink-0 flex items-center justify-center p-4 md:p-6 relative">
            <div className="relative w-full h-full flex items-center justify-center rounded-lg overflow-hidden">
              {/* Image Container */}
              <div 
                className="w-full h-full flex items-center justify-center rounded-xl overflow-hidden" 
                style={{
                  height: "calc(90vh - 12rem)",
                  minHeight: "500px"
                }}
              >
                {/* Loading state */}
                {isLoading && (
                  <div className="absolute inset-0 bg-muted/20 rounded-xl flex items-center justify-center z-10">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                      <span className="text-sm text-muted-foreground">Loading image...</span>
                    </div>
                  </div>
                )}
                
                {/* Error state */}
                {isError && (
                  <div className="absolute inset-0 bg-muted/20 rounded-xl flex items-center justify-center z-10">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <X className="h-8 w-8 text-destructive" />
                      <span className="text-sm text-destructive">Failed to load image</span>
                    </div>
                  </div>
                )}
                
                {/* Checkerboard background for transparent images */}
                {image.originalItem?.metadata?.has_transparency === "true" && (
                  <div 
                    className="absolute inset-0" 
                    style={{ 
                      backgroundImage: 'linear-gradient(45deg, #f0f0f0 25%, transparent 25%), linear-gradient(-45deg, #f0f0f0 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #f0f0f0 75%), linear-gradient(-45deg, transparent 75%, #f0f0f0 75%)',
                      backgroundSize: '20px 20px',
                      backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
                      zIndex: 0
                    }}
                  />
                )}
                
                {/* Image element */}
                {image && image.src && (
                  <OptimizedImage
                    ref={imageRef}
                    src={image.src}
                    alt={image.title || image.name}
                    width={image.originalItem?.metadata?.width ? parseInt(image.originalItem.metadata.width) : image.width || 1024}
                    height={image.originalItem?.metadata?.height ? parseInt(image.originalItem.metadata.height) : image.height || 1024}
                    className={`max-h-full max-w-full object-contain rounded-lg ${image.originalItem?.metadata?.has_transparency === "true" ? 'z-10' : ''}`}
                    onLoad={() => setIsLoading(false)}
                    onError={() => {
                      setIsLoading(false);
                      setIsError(true);
                    }}
                    priority={true}
                    loadingType="fullscreen"
                  />
                )}
                
                {/* Image controls overlay */}
                <div className="absolute bottom-4 right-4 p-1 bg-black/20 rounded-md backdrop-blur-sm">
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={toggleFullscreen}
                    className="h-8 w-8 text-white hover:bg-white/10"
                  >
                    {isFullscreen ? (
                      <Minimize className="h-4 w-4" />
                    ) : (
                      <Maximize className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </div>
          
          {/* Metadata panel */}
          <div className="w-full md:w-1/3 p-4 md:p-6 overflow-y-auto border-t md:border-t-0 md:border-l bg-muted/10">
            <div className="space-y-6">
              {/* Prompt - if it exists in metadata */}
              {image.originalItem?.metadata?.prompt && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 0L11.828 15.172a2 2 0 01-.707.707l-4.096 2.244a1 1 0 01-1.196-.27 1 1 0 01-.242-1.023l1.68-5.028a2 2 0 01.586-.586L17.414 2.586z" />
                    </svg>
                    Generation Prompt
                  </h3>
                  <div className="p-3 rounded-md border border-primary/20 bg-primary/5">
                    <p className="text-sm">{image.originalItem.metadata.prompt as string}</p>
                  </div>
                </div>
              )}
              
              {/* Description - if it exists in metadata */}
              {image.originalItem?.metadata?.description && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
                    </svg>
                    Description
                  </h3>
                  <div className="p-3 rounded-md border border-border/30 bg-muted/10">
                    <p className="text-sm">{image.originalItem.metadata.description as string}</p>
                  </div>
                </div>
              )}
              
              {/* AI Analysis Summary */}
              {image.analysis?.summary && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    AI Analysis
                  </h3>
                  <div className="p-3 rounded-md border border-border/30 bg-muted/10">
                    <p className="text-sm">{image.analysis.summary}</p>
                  </div>
                </div>
              )}
              
              {/* Products Identified */}
              {image.analysis?.products && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
                    </svg>
                    Products Identified
                  </h3>
                  <div className="p-3 rounded-md border border-border/30 bg-muted/10">
                    <p className="text-sm">{image.analysis.products}</p>
                  </div>
                </div>
              )}
              
              {/* AI Feedback */}
              {image.analysis?.feedback && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                    </svg>
                    AI Feedback
                  </h3>
                  <div className="p-3 rounded-md border border-border/30 bg-muted/10">
                    <p className="text-sm">{image.analysis.feedback}</p>
                  </div>
                </div>
              )}
              
              {/* Tags */}
              {image.tags && image.tags.length > 0 && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                    </svg>
                    Tags
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {image.tags.map((tag, index) => (
                      <Badge key={index} variant="secondary" className="flex items-center gap-1 px-2 py-1 rounded-md">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Metadata */}
              <div className="bg-card p-4 rounded-lg shadow-sm">
                <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Details
                </h3>
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <div className="p-2 rounded-md border border-border/30 bg-muted/20">
                    <dt className="text-xs text-muted-foreground mb-1">Format</dt>
                    <dd className="font-medium">{(image.name.split('.').pop() || 'Unknown').toUpperCase()}</dd>
                  </div>
                  
                  {(imageStats?.naturalWidth && imageStats?.naturalHeight) && (
                    <div className="p-2 rounded-md border border-border/30 bg-muted/20">
                      <dt className="text-xs text-muted-foreground mb-1">Resolution</dt>
                      <dd className="font-medium">{imageStats.naturalWidth} × {imageStats.naturalHeight}</dd>
                    </div>
                  )}
                  
                  {imageStats?.aspectRatio && (
                    <div className="p-2 rounded-md border border-border/30 bg-muted/20">
                      <dt className="text-xs text-muted-foreground mb-1">Aspect Ratio</dt>
                      <dd className="font-medium">{imageStats.aspectRatio.toFixed(2)}</dd>
                    </div>
                  )}
                  
                  {/* File Size removed - not needed in UI */}
                  
                  {image.originalItem?.metadata?.has_transparency === "true" && (
                    <div className="p-2 rounded-md border border-border/30 bg-muted/20">
                      <dt className="text-xs text-muted-foreground mb-1">Transparency</dt>
                      <dd className="font-medium">Yes</dd>
                    </div>
                  )}
                  
                  {(image.originalItem?.metadata?.created_at || image.originalItem?.metadata?.createdAt) && (
                    <div className="p-2 rounded-md border border-border/30 bg-muted/20">
                      <dt className="text-xs text-muted-foreground mb-1">Created</dt>
                      <dd className="font-medium">
                        {formatDistanceToNow(
                          new Date((image.originalItem.metadata.created_at || image.originalItem.metadata.createdAt) as string), 
                          { addSuffix: true }
                        )}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
              
              {/* Additional metadata */}
              {image.originalItem?.metadata && Object.entries(image.originalItem.metadata).filter(
                ([key, value]) => {
                  // Exclude core metadata fields that are displayed elsewhere
                  const excludedKeys = ['prompt', 'description', 'has_transparency', 'width', 'height', 'createdAt', 'created_at', 'tags', 'analysis', 'has_analysis', 'summary', 'products', 'feedback'];
                  // Also exclude null, undefined, empty string values, and common null-ish values
                  const hasValidValue = value !== null && value !== undefined && value !== '' && value !== 'null' && value !== 'undefined';
                  return !excludedKeys.includes(key) && hasValidValue;
                }
              ).length > 0 && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <Info className="h-4 w-4 mr-2 text-primary" />
                    Additional Information
                  </h3>
                  <div className="space-y-2">
                    {Object.entries(image.originalItem.metadata)
                      .filter(([key, value]) => {
                        // Exclude core metadata fields that are displayed elsewhere
                        const excludedKeys = ['prompt', 'description', 'has_transparency', 'width', 'height', 'createdAt', 'created_at', 'tags', 'analysis', 'has_analysis', 'summary', 'products', 'feedback'];
                        // Also exclude null, undefined, empty string values, and common null-ish values
                        const hasValidValue = value !== null && value !== undefined && value !== '' && value !== 'null' && value !== 'undefined';
                        return !excludedKeys.includes(key) && hasValidValue;
                      })
                      .map(([key, value]) => (
                        <div key={key} className="p-2 rounded-md border border-border/30 bg-muted/20">
                          <dt className="text-xs text-muted-foreground mb-1">{key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ')}</dt>
                          <dd className="font-medium text-sm break-words">{String(value)}</dd>
                        </div>
                      ))
                    }
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 