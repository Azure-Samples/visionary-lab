"use client";

import { useState, useEffect, useRef } from "react";
import { OptimizedImage } from "@/components/OptimizedImage";
import { Card } from "@/components/ui/card";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { MoreVertical, Trash2, Loader2, FolderUp } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { MediaType, deleteGalleryAsset, fetchFolders, moveAsset } from "@/services/api";
import { toast } from "sonner";

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
      [key: string]: string | number | boolean | undefined;
    };
    [key: string]: string | number | boolean | object | undefined;
  };
  width?: number;
  height?: number;
  size?: "small" | "medium" | "large";
}

interface ImageGalleryCardProps {
  image: ImageMetadata;
  index: number;
  onClick?: () => void;
  onDelete?: (imageId: string) => void;
  onMove?: (imageId: string) => void;
}

export function ImageGalleryCard({ image, index, onClick, onDelete, onMove }: ImageGalleryCardProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [aspectRatio, setAspectRatio] = useState<number | null>(null);
  const [cardSize, setCardSize] = useState<"small" | "medium" | "large">("medium");
  const cardRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isMoving, setIsMoving] = useState(false);
  const [folders, setFolders] = useState<string[]>([]);
  const [loadingFolders, setLoadingFolders] = useState(false);
  const [parsedTags, setParsedTags] = useState<string[]>([]);

  // Determine image size based on aspect ratio and index
  const determineSize = (width?: number, height?: number, index?: number) => {
    // If we have dimensions, use them to calculate aspect ratio
    if (width && height) {
      const ratio = width / height;
      
      // Landscape images (wider than they are tall)
      if (ratio > 1.3) return "large";
      
      // Portrait images (taller than they are wide)
      if (ratio < 0.8) return "small";
      
      // Square-ish images
      return "medium";
    }
    
    // Fallback: Use index to create visual variety
    if (index !== undefined) {
      if (index % 5 === 0) return "large"; // Every 5th image is large
      if (index % 3 === 0) return "small"; // Every 3rd image is small
    }
    
    return "medium";
  };

  // Get aspect ratio based on size
  const getAspectRatio = () => {
    // If we have the actual image aspect ratio, use it
    if (aspectRatio) return aspectRatio;
    
    // Otherwise use approximated ratios based on size category
    switch (cardSize) {
      case "large":
        return 16/9;
      case "small":
        return 3/4;
      case "medium":
      default:
        return 4/3; // Slightly wider than tall for medium by default
    }
  };

  // Set initial size based on metadata or index
  useEffect(() => {
    const initialSize = determineSize(image.width, image.height, index);
    setCardSize(initialSize);
    
    // If we have dimensions from metadata, set aspect ratio right away
    if (image.width && image.height) {
      setAspectRatio(image.width / image.height);
    }

    // Set tags from image metadata - should now come as clean array from API
    const processTags = () => {
      if (image.tags && image.tags.length > 0) {
        setParsedTags(image.tags);
      } else {
        setParsedTags([]);
      }
    };

    processTags();
  }, [image.width, image.height, index, image.tags]);

  // Handle image load
  const handleImageLoad = () => {
    setLoading(false);
    
    // Get actual image dimensions from loaded image
    if (imageRef.current) {
      const { naturalWidth, naturalHeight } = imageRef.current;
      
      if (naturalWidth && naturalHeight) {
        const ratio = naturalWidth / naturalHeight;
        setAspectRatio(ratio);
        
        // Update size based on actual dimensions
        const newSize = determineSize(naturalWidth, naturalHeight);
        setCardSize(newSize);
      }
    }
  };

  // Handle image error
  const handleImageError = () => {
    setLoading(false);
    setError(true);
  };

  // Handle image delete
  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent event bubbling
    
    if (!image.name) {
      toast.error("Cannot delete image", {
        description: "Missing image filename"
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
        
        // Call the onDelete callback if provided
        if (onDelete && image.id) {
          onDelete(image.id);
        }
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

  // Fetch folders when dropdown is opened
  const handleDropdownOpen = async (open: boolean) => {
    if (open && folders.length === 0 && !loadingFolders) {
      try {
        setLoadingFolders(true);
        const result = await fetchFolders(MediaType.IMAGE);
        setFolders(result.folders);
      } catch (error) {
        console.error("Failed to fetch folders:", error);
      } finally {
        setLoadingFolders(false);
      }
    }
  };

  // Handle moving an image to a folder
  const handleMove = async (folderPath: string) => {
    if (!image.name) {
      toast.error("Cannot move image", {
        description: "Missing image filename"
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
        
        // Call the onMove callback if provided
        if (onMove && image.id) {
          onMove(image.id);
        }
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

  return (
    <div 
      ref={cardRef}
      className="relative w-full mb-0"
    >
      <Card 
        className="overflow-hidden border rounded-xl group hover:shadow-md transition-all duration-200 h-full p-0 w-full bg-card"
      >
        {/* Add dropdown menu - only visible on hover */}
        <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
          <DropdownMenu onOpenChange={handleDropdownOpen}>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-8 w-8 bg-black/30 hover:bg-black/40 text-white">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuSub>
                <DropdownMenuSubTrigger disabled={isMoving || loadingFolders}>
                  {isMoving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Moving...
                    </>
                  ) : (
                    <>
                      <FolderUp className="h-4 w-4 mr-2" />
                      Move to folder
                    </>
                  )}
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent>
                  {loadingFolders ? (
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
                </DropdownMenuSubContent>
              </DropdownMenuSub>
              
              <DropdownMenuSeparator />
              
              <DropdownMenuItem 
                variant="destructive" 
                className="text-destructive cursor-pointer"
                disabled={isDeleting}
                onClick={handleDelete}
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </>
                )}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        <div onClick={onClick} className="cursor-pointer w-full h-full">
          <AspectRatio ratio={getAspectRatio()} className="bg-muted w-full h-full">
            {loading && (
              <div className="absolute inset-0 w-full h-full">
                <Skeleton className="absolute inset-0 h-full w-full rounded-none" />
                <div className="absolute bottom-0 left-0 right-0 p-4">
                  <Skeleton className="h-4 w-3/4 mb-2" />
                  <Skeleton className="h-3 w-1/2" />
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
            
            <OptimizedImage
              ref={imageRef}
              src={image.src}
              alt={image.title || image.name}
              fill
              loadingType="gallery"
              className={`object-cover transition-all duration-200 ${loading ? 'opacity-0' : 'opacity-100'} ${error ? 'hidden' : ''} ${image.originalItem?.metadata?.has_transparency === "true" ? 'z-10' : ''}`}
              onLoad={handleImageLoad}
              onError={handleImageError}
              priority={index < 8}
            />
            
            {error && (
              <div className="flex items-center justify-center h-full w-full bg-muted text-muted-foreground p-4 text-center">
                <div>
                  <p className="text-sm font-medium">Unable to load image</p>
                  <p className="text-xs mt-1">{image.name}</p>
                </div>
              </div>
            )}
            
            {/* Gradient overlay for image info */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              <div className="absolute bottom-0 left-0 right-0 p-3 text-white">
                {/* Display prompt if available, otherwise fall back to title/name */}
                <h3 className="font-medium text-sm leading-tight line-clamp-2">
                  {image.originalItem?.metadata?.prompt || image.title || image.name}
                </h3>
                
                {image.description && (
                  <p className="text-xs text-white/90 line-clamp-1 mt-1">{image.description}</p>
                )}
                
                {parsedTags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {parsedTags.slice(0, 3).map((tag, index) => (
                      <Badge key={index} variant="secondary" className="bg-black/40 text-white text-xs py-0 h-5">
                        {String(tag).replace(/"/g, '').replace(/^_|_$/g, '')}
                      </Badge>
                    ))}
                    {parsedTags.length > 3 && (
                      <Badge variant="secondary" className="bg-black/40 text-white text-xs py-0 h-5">
                        +{parsedTags.length - 3}
                      </Badge>
                    )}
                  </div>
                )}
              </div>
            </div>
          </AspectRatio>
        </div>
      </Card>
    </div>
  );
} 