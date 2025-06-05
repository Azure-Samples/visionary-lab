import { useState, useEffect, useRef } from "react";
import { Card } from "@/components/ui/card";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { cn } from "@/utils/utils";
import { PlayCircle, MoreVertical, Trash, FolderUp, Download, Loader2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { MediaType, deleteGalleryAsset, fetchFolders, moveAsset } from "@/services/api";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

interface VideoCardProps {
  src: string;
  title?: string;
  description?: string;
  size?: "small" | "medium" | "large";
  aspectRatio?: "16:9" | "4:3" | "1:1" | "9:16";
  className?: string;
  tags?: string[];
  id?: string;
  blobName?: string;
  onDelete?: () => void;
  onMove?: () => void;
  onClick?: () => void;
  autoPlay?: boolean;
}

export function VideoCard({
  src,
  description,
  aspectRatio = "16:9",
  className,
  tags,
  blobName,
  onDelete,
  onClick,
  autoPlay = true,
}: VideoCardProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [manualControl, setManualControl] = useState(false);
  const [videoWidth, setVideoWidth] = useState<number | null>(null);
  const [videoHeight, setVideoHeight] = useState<number | null>(null);
  const [actualRatio, setActualRatio] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const manualControlTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const playPauseDebounceRef = useRef<NodeJS.Timeout | null>(null);
  const initializedRef = useRef(false);
  const [isMoving, setIsMoving] = useState(false);
  const [folders, setFolders] = useState<string[]>([]);
  const [loadingFolders, setLoadingFolders] = useState(false);

  // Debounced play function to prevent rapid play/pause calls
  const debouncedPlay = () => {
    if (playPauseDebounceRef.current) {
      clearTimeout(playPauseDebounceRef.current);
    }
    
    playPauseDebounceRef.current = setTimeout(() => {
      if (videoRef.current && videoRef.current.paused) {
        // Always ensure video is muted before play on hover to avoid autoplay restrictions
        videoRef.current.muted = true;
        
        videoRef.current.play()
          .then(() => setIsPlaying(true))
          .catch(err => {
            console.error("Error playing video:", err);
            setIsPlaying(false);
          });
      }
    }, 100);
  };

  // Debounced pause function to prevent rapid play/pause calls
  const debouncedPause = () => {
    if (playPauseDebounceRef.current) {
      clearTimeout(playPauseDebounceRef.current);
    }
    
    playPauseDebounceRef.current = setTimeout(() => {
      if (videoRef.current && !videoRef.current.paused) {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    }, 100);
  };

  // Handle video loading and initial play state
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    
    // Don't try to load folder markers as videos
    if (src.includes('.folder')) {
      setIsLoading(false);
      return;
    }

    // Always set videos to muted since they have no sound
    video.muted = true;

    const handleMetadata = () => {
      const width = video.videoWidth;
      const height = video.videoHeight;
      setVideoWidth(width);
      setVideoHeight(height);
      setActualRatio(width / height);
    };

    const handleLoadStart = () => {
      setIsLoading(true);
    };

    const handleCanPlay = () => {
      setIsLoading(false);
      
      // After the video is ready to play, set the initial play state
      // We delay this to avoid play/pause race conditions during loading
      if (!initializedRef.current) {
        initializedRef.current = true;
        
        setTimeout(() => {
          if (autoPlay) {
            debouncedPlay();
          } else {
            // Make sure it's paused if autoPlay is false
            if (video && !video.paused) {
              debouncedPause();
            }
          }
        }, 100);
      }
    };

    const handleError = () => {
      setIsLoading(false);
    };

    video.addEventListener('loadedmetadata', handleMetadata);
    video.addEventListener('loadstart', handleLoadStart);
    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('error', handleError);
    
    // If video is already loaded
    if (video.readyState >= 3) {
      handleCanPlay();
    }
    if (video.readyState >= 1) {
      handleMetadata();
    }

    return () => {
      video.removeEventListener('loadedmetadata', handleMetadata);
      video.removeEventListener('loadstart', handleLoadStart);
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('error', handleError);
    };
  }, [src, autoPlay]);

  // Update play state when autoPlay changes after initialization
  useEffect(() => {
    if (initializedRef.current && !manualControl) {
      if (autoPlay) {
        debouncedPlay();
      } else {
        debouncedPause();
      }
    }
  }, [autoPlay, manualControl]);

  // Handle hover state changes for play/pause
  useEffect(() => {
    if (initializedRef.current && !autoPlay && !manualControl && videoRef.current) {
      if (isHovering) {
        debouncedPlay();
      } else {
        debouncedPause();
      }
    }
  }, [isHovering, autoPlay, manualControl]);

  // Handle play/pause toggle
  const togglePlayback = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent event bubbling
    if (!videoRef.current) return;
    
    // Set manual control to true
    setManualControl(true);
    
    // Toggle the video playback
    if (videoRef.current.paused) {
      debouncedPlay();
    } else {
      debouncedPause();
    }
  };

  // Handle delete action
  const handleDelete = async () => {
    if (!blobName) {
      toast.error("Cannot delete video", {
        description: "Missing blob name for the video"
      });
      return;
    }

    try {
      setIsDeleting(true);
      const result = await deleteGalleryAsset(blobName, MediaType.VIDEO);
      
      if (result.success) {
        toast.success("Video deleted", {
          description: "The video was successfully deleted"
        });
        
        // Call the onDelete callback if provided
        if (onDelete) {
          onDelete();
        }
      } else {
        throw new Error(result.message || "Failed to delete video");
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      toast.error("Error deleting video", {
        description: errorMessage
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Handle download action
  const handleDownload = () => {
    if (!src) {
      toast.error("Cannot download video", {
        description: "Missing video source URL"
      });
      return;
    }

    try {
      // Create an invisible anchor element to trigger the download
      const a = document.createElement('a');
      a.href = src;
      a.download = blobName || 'video-download.mp4';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      toast.success("Video download started", {
        description: "Your video is being downloaded"
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      toast.error("Error downloading video", {
        description: errorMessage
      });
    }
  };

  // Determine the actual aspect ratio from video dimensions or metadata
  const getActualAspectRatio = () => {
    // If we have the actual ratio from the video itself, use that
    if (actualRatio) return actualRatio;
    
    // If we have actual dimensions, calculate the ratio
    if (videoWidth && videoHeight) return videoWidth / videoHeight;
    
    // Check if there's an aspect ratio in the metadata (might come from the backend)
    if (aspectRatio) {
      // If it's a string like "16:9", convert it to a number
      if (typeof aspectRatio === 'string' && aspectRatio.includes(':')) {
        return getRatioFromString(aspectRatio);
      }
      // If it's already a number, just use it
      if (typeof aspectRatio === 'number') {
        return aspectRatio;
      }
    }
    
    // Default to 16:9 if nothing else is available
    return 16/9;
  };

  const getRatioFromString = (ratio: string): number => {
    switch (ratio) {
      case "16:9": return 16/9;
      case "4:3": return 4/3;
      case "1:1": return 1;
      case "9:16": return 9/16;
      default: return 16/9;
    }
  };

  // Determine size class based on prop

  // For large cards, we won't use AspectRatio's default ratio behavior
  // and instead let the video fill the space completely

  // Helper function to get a variant for a tag
  const getTagVariant = (tag: string): "default" | "secondary" | "outline" | "destructive" => {
    // Map specific tags to specific variants or use a simple rotation
    const tagVariants: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
      "AI Generated": "default",
      "Landscape": "secondary",
      "Portrait": "secondary",
      "Nature": "outline",
      "Urban": "outline",
      "Abstract": "default",
      "People": "secondary",
      "Architecture": "outline",
      "Animals": "destructive",
      "Technology": "default",
    };
    
    return tagVariants[tag] || "outline";
  };

  // Skeleton loader for video content
  const renderSkeleton = () => (
    <div className="absolute inset-0">
      <Skeleton className="h-full w-full" />
    </div>
  );

  // Reset manualControl after mouse leaves the video for a while
  const handleMouseLeave = () => {
    setIsHovering(false);
    
    // Clear any existing timeout
    if (manualControlTimeoutRef.current) {
      clearTimeout(manualControlTimeoutRef.current);
    }
    
    // Set a new timeout to reset manual control after 3 seconds
    manualControlTimeoutRef.current = setTimeout(() => {
      setManualControl(false);
      
      // If autoplay is off and no manual control, ensure video is paused when not hovering
      if (!autoPlay && videoRef.current && !videoRef.current.paused) {
        debouncedPause();
      }
    }, 3000); // 3 seconds
  };
  
  const handleMouseEnter = () => {
    setIsHovering(true);
    
    // Clear any existing timeout
    if (manualControlTimeoutRef.current) {
      clearTimeout(manualControlTimeoutRef.current);
      manualControlTimeoutRef.current = null;
    }
  };
  
  // Clean up all timeouts on unmount
  useEffect(() => {
    return () => {
      if (manualControlTimeoutRef.current) {
        clearTimeout(manualControlTimeoutRef.current);
      }
      if (playPauseDebounceRef.current) {
        clearTimeout(playPauseDebounceRef.current);
      }
    };
  }, []);

  // Fetch folders when dropdown is opened
  const handleDropdownOpen = async (open: boolean) => {
    if (open && folders.length === 0 && !loadingFolders) {
      try {
        setLoadingFolders(true);
        const result = await fetchFolders(MediaType.VIDEO);
        setFolders(result.folders);
      } catch (error) {
        console.error("Failed to fetch folders:", error);
      } finally {
        setLoadingFolders(false);
      }
    }
  };

  // Handle moving a video to a folder
  const handleMove = async (folderPath: string) => {
    if (!blobName) {
      toast.error("Cannot move video", {
        description: "Missing blob name for the video"
      });
      return;
    }

    try {
      setIsMoving(true);
      const result = await moveAsset(blobName, folderPath, MediaType.VIDEO);
      
      if (result.success) {
        toast.success("Video moved", {
          description: `The video was successfully moved to "${folderPath}"`
        });
        
        // Call the onDelete callback to refresh the gallery
        // This is the same as what happens after deletion since we need to refresh the list
        if (onDelete) {
          onDelete();
        }
      } else {
        throw new Error(result.message || "Failed to move video");
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      toast.error("Error moving video", {
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
        className={cn(
          "overflow-hidden border rounded-xl group hover:shadow-md transition-all duration-200 h-full p-0 w-full bg-card",
          className,
          onClick && "cursor-pointer"
        )}
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
              
              <DropdownMenuItem onClick={handleDownload}>
                <Download className="h-4 w-4 mr-2" />
                Download
              </DropdownMenuItem>
              
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
                    <Trash className="h-4 w-4 mr-2" />
                    Delete
                  </>
                )}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        <div 
          onClick={(e) => {
            // Don't trigger onClick if the user is clicking on the video controls
            if ((e.target as HTMLElement).closest('.video-controls')) {
              return;
            }
            // Call onClick if provided
            if (onClick) {
              onClick();
            }
          }} 
          className="w-full h-full"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <AspectRatio ratio={getActualAspectRatio()} className="bg-muted w-full h-full">
            {/* Video container */}
            <div className="absolute inset-0 flex items-center justify-center w-full h-full">
              {isLoading && renderSkeleton()}
              
              <video
                ref={videoRef}
                src={src}
                className={cn(
                  "absolute inset-0 object-cover w-full h-full transition-opacity duration-200",
                  isLoading ? "opacity-0" : "opacity-100"
                )}
                playsInline
                loop
                muted={true}
                onClick={(e) => {
                  // Allow video click events without triggering the parent onClick
                  e.stopPropagation();
                  togglePlayback(e);
                }}
              />
              
              {/* Play/pause button overlay - this shouldn't trigger the detail view */}
              <div 
                className={cn(
                  "absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 video-controls",
                  isPlaying ? "bg-black/10" : "bg-black/30"
                )}
                onClick={(e) => {
                  e.stopPropagation();
                  togglePlayback(e);
                }}
              >
                <PlayCircle 
                  className={cn(
                    "h-16 w-16 text-white/80 transition-opacity duration-200",
                    isPlaying ? "opacity-0" : "opacity-80"
                  )} 
                />
              </div>
              
              {/* ... rest of the content */}
            </div>
            
            {/* Video details overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              <div className="absolute bottom-0 left-0 right-0 p-3 text-white">
                {/* Title removed as requested */}
                
                {description && (
                  <p className="text-xs text-white/90 line-clamp-1">{description}</p>
                )}
                
                {/* Display tags */}
                {tags && tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {tags.slice(0, 3).map((tag, index) => (
                      <Badge 
                        key={index} 
                        variant={getTagVariant(tag)} 
                        className="bg-black/40 text-white text-xs py-0 h-5"
                      >
                        {tag}
                      </Badge>
                    ))}
                    {tags.length > 3 && (
                      <Badge variant="secondary" className="bg-black/40 text-white text-xs py-0 h-5">
                        +{tags.length - 3}
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