"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { 
  X, ChevronLeft, ChevronRight, Play, Pause, 
  Download, Trash2, FolderUp, Eye, Loader2, Maximize, Minimize 
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
import { MediaType, deleteGalleryAsset, VideoAnalysisResponse, fetchFolders, moveAsset, analyzeAndUpdateVideoMetadata } from "@/services/api";
import { VideoMetadata } from "@/utils/gallery-utils";

interface VideoDetailViewProps {
  video: VideoMetadata | null;
  videos: VideoMetadata[];
  onClose: () => void;
  onDelete: (videoId: string) => void;
  onMove?: (videoId: string) => void;
  onNavigate?: (direction: 'prev' | 'next', index: number) => void;
}

export function VideoDetailView({ 
  video, 
  videos, 
  onClose, 
  onDelete,
  onMove,
  onNavigate
}: VideoDetailViewProps) {
  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // State
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [, setVolume] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isMoving, setIsMoving] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<VideoAnalysisResponse | null>(null);
  const [folders, setFolders] = useState<string[]>([]);
  const [isFoldersLoading, setIsFoldersLoading] = useState(false);
  const [isError, setIsError] = useState(false);

  // Load folders when dropdown is opened
  const loadFolders = async () => {
    if (folders.length > 0) return;
    
    try {
      setIsFoldersLoading(true);
      const result = await fetchFolders(MediaType.VIDEO);
      setFolders(result.folders);
    } catch (error) {
      console.error("Failed to fetch folders:", error);
      toast.error("Failed to load folders");
    } finally {
      setIsFoldersLoading(false);
    }
  };

  // Video player controls
  const togglePlay = useCallback(() => {
    if (!videoRef.current) return;
    
    try {
      if (isPlaying) {
        videoRef.current.pause();
        setIsPlaying(false);
      } else {
        const playPromise = videoRef.current.play();
        
        if (playPromise !== undefined) {
          playPromise
            .then(() => {
              setIsPlaying(true);
            })
            .catch(error => {
              console.error("Failed to play video:", error);
              setIsPlaying(false);
              
              // Show more helpful error message based on error
              if (error.name === "NotAllowedError") {
                toast.error("Autoplay blocked", {
                  description: "Browser blocked autoplay. Click play button to watch."
                });
              } else {
                toast.error("Failed to play video", {
                  description: "There was a problem playing this video. Try again."
                });
              }
            });
        }
      }
    } catch (error) {
      console.error("Toggle play error:", error);
      toast.error("Video playback error");
    }
  }, [isPlaying]);

  const toggleMute = useCallback(() => {
    if (!videoRef.current) return;
    
    const newMutedState = !isMuted;
    videoRef.current.muted = newMutedState;
    setIsMuted(newMutedState);
  }, [isMuted]);

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

  // Handle video events
  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement) return;
    
    // Clear any existing event listeners before setting new ones
    const clearListeners = () => {
      videoElement.removeEventListener('timeupdate', handleTimeUpdate);
      videoElement.removeEventListener('durationchange', handleDurationChange);
      videoElement.removeEventListener('play', handlePlay);
      videoElement.removeEventListener('pause', handlePause);
      videoElement.removeEventListener('volumechange', handleVolumeChange);
      videoElement.removeEventListener('loadeddata', handleLoadedData);
      videoElement.removeEventListener('error', handleError);
    };
    
    // Define event handlers
    const handleTimeUpdate = () => {
      setCurrentTime(videoElement.currentTime);
    };
    
    const handleDurationChange = () => {
      setDuration(videoElement.duration);
    };
    
    const handlePlay = () => {
      setIsPlaying(true);
    };
    
    const handlePause = () => {
      setIsPlaying(false);
    };
    
    const handleVolumeChange = () => {
      setVolume(videoElement.volume);
      setIsMuted(videoElement.muted);
    };

    const handleLoadedData = () => {
      console.log("Video loaded successfully");
      setIsLoading(false);
      setIsError(false);
      
      // Immediately check if the video has a valid duration
      if (!isNaN(videoElement.duration) && videoElement.duration > 0) {
        setDuration(videoElement.duration);
      }
    };

    const handleError = () => {
      console.error("Video error:", videoElement.error);
      setIsLoading(false);
      setIsError(true);
    };

    // Clear existing listeners (just in case)
    clearListeners();
    
    // Add event listeners
    videoElement.addEventListener('timeupdate', handleTimeUpdate);
    videoElement.addEventListener('durationchange', handleDurationChange);
    videoElement.addEventListener('play', handlePlay);
    videoElement.addEventListener('pause', handlePause);
    videoElement.addEventListener('volumechange', handleVolumeChange);
    videoElement.addEventListener('loadeddata', handleLoadedData);
    videoElement.addEventListener('error', handleError);
    
    // Also check if the video is already loaded
    if (videoElement.readyState >= 3) {
      handleLoadedData();
    }
    
    // Clean up
    return clearListeners;
  }, [video]); // Include video in dependencies to reset listeners when video changes

  // Add effect to reset state when video changes
  useEffect(() => {
    if (video) {
      // Reset states when video changes
      setIsLoading(true);
      setCurrentTime(0);
      setDuration(0);
      setIsPlaying(false);
      setIsError(false);
      
      // Sora 2 videos include audio
      setIsMuted(false);

      // If the video element already has its data loaded
      if (videoRef.current) {
        // Reset the current time to start from the beginning
        videoRef.current.currentTime = 0;

        // Sora 2 videos include audio
        videoRef.current.muted = false;
        
        // If video data is already loaded, update the loading state
        if (videoRef.current.readyState >= 3) {
          setIsLoading(false);
          
          // Start playing automatically after a short delay to ensure proper loading
          setTimeout(() => {
            if (videoRef.current) {
              videoRef.current.play()
                .then(() => {
                  setIsPlaying(true);
                })
                .catch(error => {
                  console.log("Auto-play prevented:", error);
                  // Auto-play might be blocked by browser policy, which is fine
                });
            }
          }, 300);
        }
        
        // When we get a new video, the browser might have retained autoplay blocking status
        // from previous videos. This helps start fresh.
        videoRef.current.load();
      }
    }
  }, [video]);

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

  // Handle keyboard navigation
  // Navigate to another video - moved before useEffect to avoid temporal dead zone
  const navigateVideo = useCallback((direction: 'prev' | 'next') => {
    if (!video || videos.length <= 1) return;
    
    const currentIndex = videos.findIndex(v => v.id === video.id);
    if (currentIndex === -1) return;
    
    let newIndex: number;
    if (direction === 'prev') {
      newIndex = currentIndex === 0 ? videos.length - 1 : currentIndex - 1;
    } else {
      newIndex = currentIndex === videos.length - 1 ? 0 : currentIndex + 1;
    }
    
    // The parent component that owns the VideoDetailView should handle the navigation
    // by updating the fullscreenVideo state with videos[newIndex].
    // We'll just call the onNavigate callback if available.
    if (onNavigate) {
      onNavigate(direction, newIndex);
    }
  }, [video, videos, onNavigate]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check if the event target is an input field, textarea, or element with contentEditable
      const target = e.target as HTMLElement;
      const isEditableTarget = 
        target.tagName === 'INPUT' || 
        target.tagName === 'TEXTAREA' || 
        target.getAttribute('contenteditable') === 'true';
      
      // Only process keyboard shortcuts if not typing in a form field
      if (isEditableTarget) {
        return;
      }
      
      switch (e.key) {
        case 'Escape':
          // Only handle Escape if we're not in fullscreen
          if (!document.fullscreenElement) {
            onClose();
          }
          break;
        case 'ArrowLeft':
          if (video && videos.length > 1) {
            navigateVideo('prev');
          }
          break;
        case 'ArrowRight':
          if (video && videos.length > 1) {
            navigateVideo('next');
          }
          break;
        case ' ':
          // Space to toggle play/pause
          togglePlay();
          // Prevent page scroll
          e.preventDefault();
          break;
        case 'm':
          // 'M' to toggle mute
          toggleMute();
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
  }, [video, videos, navigateVideo, onClose, togglePlay, toggleMute]);

  // Handle video deletion
  const handleDelete = async () => {
    if (!video || !video.name) {
      toast.error("Cannot delete video", {
        description: "Missing video information"
      });
      return;
    }

    try {
      setIsDeleting(true);
      const result = await deleteGalleryAsset(video.name, MediaType.VIDEO);
      
      if (result.success) {
        toast.success("Video deleted", {
          description: "The video was successfully deleted"
        });
        
        // Notify parent component
        onDelete(video.id);
        
        // Close the detail view
        onClose();
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

  // Add useEffect to check for analysis metadata when video changes
  useEffect(() => {
    if (video && video.originalItem && video.originalItem.metadata) {
      const metadata = video.originalItem.metadata;
      
      // Check if this video has already been analyzed (stored in metadata)
      if (metadata.has_analysis === "true") {
        // Reconstruct analysis result from metadata
        const analysisFromMetadata: VideoAnalysisResponse = {
          summary: metadata.analysis_summary as string || "",
          products: metadata.analysis_products as string || "",
          // Convert comma-separated tags back to array
          tags: metadata.analysis_tags ? (metadata.analysis_tags as string).split(",") : [],
          feedback: metadata.analysis_feedback as string || ""
        };
        
        // Update analysis state
        setAnalysisResult(analysisFromMetadata);
      } else {
        // Reset analysis result if no metadata analysis exists
        setAnalysisResult(null);
      }
    }
  }, [video]);

  // Update handleAnalyze to save results to metadata
  const handleAnalyze = async () => {
    if (!video || !video.name) {
      toast.error("Cannot analyze video", {
        description: "Missing video information"
      });
      return;
    }

    try {
      setIsAnalyzing(true);
      toast("Analyzing video...", {
        description: "This may take a moment"
      });
      
      // Use the combined analyze and update function
      const result = await analyzeAndUpdateVideoMetadata(video.name);
      setAnalysisResult(result.analysis);
      
      toast.success("Video analysis complete", {
        description: "The analysis has been added to video metadata."
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "An unknown error occurred";
      toast.error("Error analyzing video", {
        description: errorMessage
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Handle downloading the video
  const handleDownload = () => {
    if (!video || !video.src) {
      toast.error("Cannot download video", {
        description: "Missing video source"
      });
      return;
    }

    try {
      const a = document.createElement('a');
      a.href = video.src;
      a.download = video.name || 'video-download.mp4';
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

  // Handle moving the video to a folder
  const handleMove = async (folderPath: string) => {
    if (!video || !video.name) {
      toast.error("Cannot move video", {
        description: "Missing video information"
      });
      return;
    }

    try {
      setIsMoving(true);
      const result = await moveAsset(video.name, folderPath, MediaType.VIDEO);
      
      if (result.success) {
        toast.success("Video moved", {
          description: `The video was successfully moved to "${folderPath}"`
        });
        
        // Notify parent component if provided
        if (onMove) {
          onMove(video.id);
        }
        
        // Close the detail view
        onClose();
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

  // Format time in MM:SS format
  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  // Display analysis results

  // If no video is provided, don't render anything
  if (!video) return null;

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
              onClick={() => navigateVideo('prev')}
              className="h-8 w-8"
              disabled={videos.length <= 1 || isLoading}
            >
              <ChevronLeft className="h-5 w-5" />
              <span className="sr-only">Previous video</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigateVideo('next')}
              className="h-8 w-8"
              disabled={videos.length <= 1 || isLoading}
            >
              <ChevronRight className="h-5 w-5" />
              <span className="sr-only">Next video</span>
            </Button>
            {isLoading && (
              <div className="ml-2 flex items-center">
                <Loader2 className="h-4 w-4 mr-2 animate-spin text-primary" />
                <span className="text-xs text-muted-foreground">Loading video...</span>
              </div>
            )}
          </div>
          
          {/* Display title in the header */}
          {video && (
            <div className="hidden md:block max-w-lg overflow-hidden text-ellipsis whitespace-nowrap">
              <h2 className="text-lg font-medium">{video.title || 'Untitled Video'}</h2>
              {video.description && (
                <p className="text-xs text-muted-foreground truncate">{video.description}</p>
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
        
        {/* Video Player */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          <div className="w-full md:w-2/3 flex-shrink-0 flex items-center justify-center p-4 md:p-6 relative">
            <div className="relative w-full h-full flex items-center justify-center rounded-lg overflow-hidden">
              {/* Video Container */}
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
                      <span className="text-sm text-muted-foreground">Loading video...</span>
                    </div>
                  </div>
                )}
                
                {/* Error state */}
                {isError && (
                  <div className="absolute inset-0 bg-muted/20 rounded-xl flex items-center justify-center z-10">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <X className="h-8 w-8 text-destructive" />
                      <span className="text-sm text-destructive">Failed to load video</span>
                    </div>
                  </div>
                )}
                
                {/* Video element */}
                {video && video.src && (
                  <video
                    key={video.src}
                    ref={videoRef}
                    src={video.src}
                    className="w-full h-full object-contain rounded-lg"
                    controls={false}
                    preload="auto"
                    playsInline
                    muted={false}
                    onLoadedData={() => {
                      setIsLoading(false);
                      setIsError(false);
                    }}
                    onError={(e) => {
                      console.error("Video error:", e);
                      setIsLoading(false);
                      setIsError(true);
                    }}
                  />
                )}
                
                {/* Add central play button when video is paused */}
                {video && !isPlaying && !isLoading && !isError && (
                  <div 
                    className="absolute inset-0 flex items-center justify-center cursor-pointer"
                    onClick={togglePlay}
                  >
                    <div className="w-20 h-20 bg-black/40 rounded-full flex items-center justify-center hover:bg-black/60 transition-colors">
                      <Play className="h-10 w-10 text-white ml-1" />
                    </div>
                  </div>
                )}
                
                {/* Video controls overlay */}
                <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/60 to-transparent opacity-70 hover:opacity-100 transition-opacity duration-200">
                  {/* Progress bar */}
                  <div 
                    className="w-full h-1 bg-white/20 rounded-full mb-3 relative cursor-pointer"
                    onClick={(e) => {
                      if (!videoRef.current) return;
                      
                      const rect = e.currentTarget.getBoundingClientRect();
                      const position = (e.clientX - rect.left) / rect.width;
                      
                      if (videoRef.current.duration) {
                        videoRef.current.currentTime = position * videoRef.current.duration;
                      }
                    }}
                  >
                    <div 
                      className="absolute inset-y-0 left-0 bg-primary rounded-full" 
                      style={{ width: `${(currentTime / (duration || 1)) * 100}%` }}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    {/* Left controls */}
                    <div className="flex items-center gap-2">
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={togglePlay}
                        className="h-8 w-8 bg-black/50 text-white hover:bg-black/70"
                      >
                        {isPlaying ? (
                          <Pause className="h-4 w-4" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                      </Button>
                      
                      <span className="text-xs text-white">
                        {formatTime(currentTime)} / {formatTime(duration)}
                      </span>
                    </div>
                    
                    {/* Right controls */}
                    <div className="flex items-center gap-2">
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={toggleFullscreen}
                        className="h-8 w-8 bg-black/50 text-white hover:bg-black/70"
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
            </div>
          </div>
          
          {/* Metadata panel */}
          <div className="w-full md:w-1/3 p-4 md:p-6 overflow-y-auto border-t md:border-t-0 md:border-l bg-muted/10">
            <div className="space-y-6">
              {/* Prompt - if it exists in metadata */}
              {video.originalItem?.metadata?.prompt && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 0L11.828 15.172a2 2 0 01-.707.707l-4.096 2.244a1 1 0 01-1.196-.27 1 1 0 01-.242-1.023l1.68-5.028a2 2 0 01.586-.586L17.414 2.586z" />
                    </svg>
                    Generation Prompt
                  </h3>
                  <div className="p-3 rounded-md border border-primary/20 bg-primary/5">
                    <p className="text-sm">{video.originalItem.metadata.prompt as string}</p>
                  </div>
                </div>
              )}
              
              {/* Tags */}
              {video.tags && video.tags.length > 0 && (
                <div className="bg-card p-4 rounded-lg shadow-sm">
                  <h3 className="text-sm font-medium mb-3 flex items-center border-b pb-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                    </svg>
                    Tags
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {video.tags.map((tag, index) => (
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
                    <dd className="font-medium">MP4 Video</dd>
                  </div>
                  
                  {video.width && video.height && (
                    <div className="p-2 rounded-md border border-border/30 bg-muted/20">
                      <dt className="text-xs text-muted-foreground mb-1">Resolution</dt>
                      <dd className="font-medium">{video.width} x {video.height}</dd>
                    </div>
                  )}
                  
                  {duration > 0 && (
                    <div className="p-2 rounded-md border border-border/30 bg-muted/20">
                      <dt className="text-xs text-muted-foreground mb-1">Duration</dt>
                      <dd className="font-medium">{formatTime(duration)}</dd>
                    </div>
                  )}
                  
                  {video.originalItem?.metadata?.createdAt && (
                    <div className="p-2 rounded-md border border-border/30 bg-muted/20">
                      <dt className="text-xs text-muted-foreground mb-1">Created</dt>
                      <dd className="font-medium">{formatDistanceToNow(new Date(video.originalItem.metadata.createdAt as string), { addSuffix: true })}</dd>
                    </div>
                  )}
                </dl>
              </div>
              
              {/* Analysis results */}
              <div className="bg-card p-4 rounded-lg shadow-sm">
                <div className="flex justify-between items-center border-b pb-2 mb-3">
                  <h3 className="text-sm font-medium flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Analysis
                  </h3>
                  {!analysisResult && !video.analysis?.analyzed && (
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={handleAnalyze}
                      disabled={isAnalyzing}
                      className="h-8"
                    >
                      {isAnalyzing ? (
                        <>
                          <Loader2 className="h-3 w-3 mr-2 animate-spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>Analyze Video</>
                      )}
                    </Button>
                  )}
                </div>
                
                {/* Show analysis from metadata first, then from analysisResult state */}
                {(video.analysis?.analyzed || analysisResult) ? (
                  <div className="space-y-4 text-sm">
                    {/* Use metadata analysis if available, otherwise use analysisResult */}
                    {(video.analysis?.summary || analysisResult?.summary) && (
                      <div className="p-3 rounded-md border border-border/30 bg-muted/20">
                        <h4 className="font-medium text-xs text-primary mb-1">Summary</h4>
                        <p className="text-sm">{video.analysis?.summary || analysisResult?.summary}</p>
                      </div>
                    )}
                    
                    {(video.analysis?.products || analysisResult?.products) && (
                      <div className="p-3 rounded-md border border-border/30 bg-muted/20">
                        <h4 className="font-medium text-xs text-primary mb-1">Products/Brands</h4>
                        <p className="text-sm">{video.analysis?.products || analysisResult?.products}</p>
                      </div>
                    )}
                    
                    {((video.analysis?.tags && video.analysis.tags.length > 0) || (analysisResult?.tags && analysisResult.tags.length > 0)) && (
                      <div className="p-3 rounded-md border border-border/30 bg-muted/20">
                        <h4 className="font-medium text-xs text-primary mb-2">AI Tags</h4>
                        <div className="flex flex-wrap gap-2">
                          {(video.analysis?.tags || analysisResult?.tags || []).map((tag, index) => (
                            <Badge key={index} variant="outline" className="bg-background">{tag}</Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {(video.analysis?.feedback || analysisResult?.feedback) && (
                      <div className="p-3 rounded-md border border-border/30 bg-muted/20">
                        <h4 className="font-medium text-xs text-primary mb-1">Feedback</h4>
                        <p className="text-sm">{video.analysis?.feedback || analysisResult?.feedback}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center p-6 text-center bg-muted/10 rounded-md border border-dashed border-border/50">
                    <Eye className="h-8 w-8 text-muted-foreground mb-2 opacity-50" />
                    <p className="text-sm text-muted-foreground">No analysis available for this video yet.</p>
                    <p className="text-xs text-muted-foreground mt-1">Click &ldquo;Analyze Video&rdquo; to generate insights.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 