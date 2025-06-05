"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { PageHeader } from "@/components/page-header";
import { Loader2, RefreshCw, Clock, Video, VideoOff, FolderIcon, FileVideo } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatDistanceToNow } from "date-fns";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { fetchVideos, VideoMetadata } from "@/utils/gallery-utils";
import { VideoCard } from "@/components/VideoCard";
import { VideoOverlay } from "@/components/VideoOverlay";
import { useVideoQueue, registerGalleryRefreshCallback, unregisterGalleryRefreshCallback } from "@/context/video-queue-context";
import { protectImagePrompt, fetchFolders, MediaType } from "@/services/api";
import { useImageSettings } from "@/context/image-settings-context";
import { SlideTransition } from "@/components/ui/page-transition";
import { VideoDetailView } from "@/components/VideoDetailView";

// Separate component that uses useSearchParams
function NewVideoPageContent() {
  const searchParams = useSearchParams();
  const folderParam = searchParams.get('folder');
  
  const [videos, setVideos] = useState<VideoMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [autoPlay, setAutoPlay] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [lastRefreshedText, setLastRefreshedText] = useState<string>("Never refreshed");
  const [lastCompletedJobId, setLastCompletedJobId] = useState<string | null>(null);
  const limit = 50;
  
  // Add state for folder selection and video generation
  const [folders, setFolders] = useState<string[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>(folderParam || "root");
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Get video generation context
  const { addToQueue, queueItems } = useVideoQueue();
  const imageSettings = useImageSettings();
  
  // Load folders when component mounts
  useEffect(() => {
    const loadFoldersList = async () => {
      try {
        const result = await fetchFolders(MediaType.VIDEO);
        setFolders(result.folders);
      } catch (error) {
        console.error("Error loading folders:", error);
      }
    };
    
    loadFoldersList();
  }, []);
  
  // Handle folder selection change and load videos when folder changes
  useEffect(() => {
    // Set the selected folder and load videos whenever the folder parameter changes
    setSelectedFolder(folderParam || "root");
    setLoading(true); // Show loading state
    
    // Small delay to ensure any navigation transitions complete first
    const loadTimer = setTimeout(() => {
      // Use fetchVideos directly to avoid dependency on loadVideos
      fetchVideos(limit, 0, folderParam || undefined)
        .then((fetchedVideos) => {
          setVideos(fetchedVideos);
          const now = new Date();
          setLastRefreshed(now);
          setLastRefreshedText(`Last refreshed ${formatDistanceToNow(now, { addSuffix: true })}`);
          setHasMore(fetchedVideos.length >= limit);
          setOffset(0);
        })
        .catch((error) => {
          console.error("Failed to load videos:", error);
          toast.error("Error loading videos", {
            description: "Failed to load videos from the gallery"
          });
        })
        .finally(() => {
          setLoading(false);
        });
    }, 50);
    
    return () => clearTimeout(loadTimer);
  }, [folderParam, limit]); // Correctly list dependencies

  const loadVideos = useCallback(async (resetVideos = true, isAutoRefresh = false) => {
    // If we're already in a loading state (e.g., from folder change), don't set it again
    if (resetVideos) {
      if (!isAutoRefresh && !loading) {
        setLoading(true);
      } else if (isAutoRefresh) {
        setIsRefreshing(true);
      }
      setOffset(0);
    } else {
      setIsLoadingMore(true);
    }

    try {
      const fetchedVideos = await fetchVideos(limit, resetVideos ? 0 : offset, folderParam || undefined);
      
      if (resetVideos) {
        // Compare with previous videos to see if we have new content
        const hasNewVideos = fetchedVideos.some(newVideo => 
          !videos.some(existingVideo => existingVideo.id === newVideo.id)
        );
        
        const previousCount = videos.length;
        setVideos(fetchedVideos);
        
        // Update last refreshed time
        const now = new Date();
        setLastRefreshed(now);
        setLastRefreshedText(`Last refreshed ${formatDistanceToNow(now, { addSuffix: true })}`);
        
        // Show feedback about new videos if any were found and it's not an auto-refresh
        if (hasNewVideos && !isAutoRefresh && previousCount > 0 && fetchedVideos.length > previousCount) {
          const newCount = fetchedVideos.length - previousCount;
          toast.success(`${newCount} new video${newCount !== 1 ? 's' : ''} found`, {
            description: "New content has been added to your gallery"
          });
        } else if (!isAutoRefresh && fetchedVideos.length === 0 && previousCount > 0) {
          // If videos were deleted or filtered out
          toast.info("No videos in this view", {
            description: folderParam ? "This folder is currently empty" : "No videos found in the gallery"
          });
        }
      } else {
        const prevCount = videos.length;
        setVideos(prevVideos => [...prevVideos, ...fetchedVideos]);
        
        // Show toast for added videos when loading more
        if (fetchedVideos.length > 0) {
          toast.info(`Loaded ${fetchedVideos.length} more video${fetchedVideos.length !== 1 ? 's' : ''}`, {
            description: `Now showing ${prevCount + fetchedVideos.length} videos in total`,
            duration: 3000
          });
        }
      }
      
      // If we got fewer videos than the limit, there are no more videos to load
      setHasMore(fetchedVideos.length >= limit);
      
      // Update offset for next page
      if (!resetVideos) {
        setOffset(prevOffset => prevOffset + limit);
      }
    } catch (error) {
      console.error("Failed to load videos:", error);
      toast.error("Error loading videos", {
        description: "Failed to load videos from the gallery"
      });
    } finally {
      setLoading(false);
      setIsLoadingMore(false);
      setIsRefreshing(false);
    }
  }, [limit, offset, folderParam, videos.length]);

  // Register for upload completion notifications
  useEffect(() => {
    // Create a callback function to refresh the gallery
    const refreshGalleryCallback = () => {
      // Check if we're already loading to avoid duplicate refreshes
      if (!loading && !isRefreshing) {
        loadVideos(true, true);
      }
    };
    
    // Register the callback when the component mounts
    registerGalleryRefreshCallback(refreshGalleryCallback);
    
    // Unregister the callback when the component unmounts
    return () => {
      unregisterGalleryRefreshCallback(refreshGalleryCallback);
    };
  }, [loading, isRefreshing, loadVideos]);

  // Toggle auto-refresh
  const toggleAutoRefresh = () => {
    setAutoRefresh(prev => !prev);
  };

  // Toggle auto-play
  const toggleAutoPlay = () => {
    setAutoPlay(prev => !prev);
  };

  // Handle auto refresh toggle
  useEffect(() => {
    if (autoRefresh) {
      // Set up a refresh interval (every 30 seconds)
      // Use a function reference that won't change between renders
      const refreshFn = () => {
        if (!isRefreshing && !loading) {
          setIsRefreshing(true);
          // Use a promise to handle the async operation
          fetchVideos(limit, 0, folderParam || undefined)
            .then((fetchedVideos) => {
              setVideos(fetchedVideos);
              const now = new Date();
              setLastRefreshed(now);
              setLastRefreshedText(`Last refreshed ${formatDistanceToNow(now, { addSuffix: true })}`);
              setHasMore(fetchedVideos.length >= limit);
            })
            .catch((error) => {
              console.error("Failed to auto-refresh videos:", error);
            })
            .finally(() => {
              setIsRefreshing(false);
            });
        }
      };
      
      const interval = setInterval(refreshFn, 30000); // 30 seconds
      
      setRefreshInterval(interval);
      
      // Cleanup interval on component unmount or when autoRefresh is turned off
      return () => {
        if (interval) clearInterval(interval);
      };
    } else if (refreshInterval) {
      // Clear the interval if auto refresh is turned off
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
  }, [autoRefresh, limit, folderParam]);

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

  // Track jobs in progress to avoid immediate refreshes
  const [jobsInProgress, setJobsInProgress] = useState<Record<string, boolean>>({});
  
  // Watch for completion of videos that were actively being generated
  useEffect(() => {
    if (!queueItems || queueItems.length === 0) return;
    
    // Check for items that are fully complete (including uploads)
    const uploadedJobs = queueItems.filter(
      item => item.status === "completed" && 
             item.uploadComplete === true && 
             jobsInProgress[item.id] && 
             item.id !== lastCompletedJobId
    );
    
    if (uploadedJobs.length > 0) {
      // Take the most recent completed job
      const latestJob = uploadedJobs[uploadedJobs.length - 1];
      
      // Update tracking
      const updatedJobsInProgress = {...jobsInProgress};
      uploadedJobs.forEach(job => {
        delete updatedJobsInProgress[job.id];
      });
      setJobsInProgress(updatedJobsInProgress);
      
      // Save this job ID to avoid duplicate refreshes
      setLastCompletedJobId(latestJob.id);
      
      // Wait a moment for backend indexing to complete
      setTimeout(() => {
        // Don't refresh unnecessarily if we just refreshed or are loading
        if (!loading && !isRefreshing) {
          // Do a full refresh of the gallery
          loadVideos(true);
          
          // Don't show additional toast here - the video queue context already shows success notification
        }
      }, 1000);
    }
  }, [queueItems, jobsInProgress, loading, isRefreshing, folderParam, loadVideos]);

  // No need for a separate loading effect - videos are loaded when the folder changes
  // and can be refreshed manually or with auto-refresh
  
  // Function to handle video deletion
  const handleVideoDeleted = (deletedVideoName: string) => {
    // Remove the deleted video from the state using the unique video name (blob name)
    setVideos(prevVideos => prevVideos.filter(video => video.name !== deletedVideoName));
    
    // If we've deleted a video, we might want to load another one to replace it
    if (hasMore && videos.length < limit * 2) {
      loadMoreVideos();
    }
  };

  // Function to load more videos
  const loadMoreVideos = () => {
    if (!hasMore || isLoadingMore) return;
    loadVideos(false);
  };

  // Generate skeleton placeholders for loading state
  const renderSkeletons = (count: number) => {
    return Array.from({ length: count }).map((_, index) => (
      <div key={`skeleton-${index}`} className="mb-6">
        <Card className="overflow-hidden bg-black p-0 border-0 rounded-xl">
          <AspectRatio ratio={16/9} className="bg-muted">
            <Skeleton className="h-full w-full rounded-none" />
          </AspectRatio>
          <div className="p-4 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-full" />
          </div>
        </Card>
      </div>
    ));
  };

  // Function to generate sample tags for videos
  const generateTagsForVideo = (video: VideoMetadata, index: number): string[] => {
    // First, check if we have real analysis tags
    if (video.analysis?.tags && video.analysis.tags.length > 0) {
      return video.analysis.tags;
    }
    
    // If the video already has tags from other sources, use those
    if (video.tags && video.tags.length > 0) {
      return video.tags;
    }
    
    // Extract tags from metadata if available
    if (video.originalItem?.metadata?.tags) {
      try {
        const tagString = video.originalItem.metadata.tags;
        if (typeof tagString === 'string') {
          return JSON.parse(tagString);
        }
      } catch (e) {
        console.warn("Failed to parse tags from metadata", e);
      }
    }
    
    // If no real tags are available, return empty array instead of dummy tags
    return [];
  };

  // Group videos into columns for masonry layout
  const groupVideosIntoColumns = (numCols = 3) => {
    const columns: VideoMetadata[][] = Array.from({ length: numCols }, () => []);
    
    // Distribute videos across columns
    videos.forEach((video, index) => {
      const columnIndex = index % numCols;
      columns[columnIndex].push(video);
    });
    
    return columns;
  };

  const columns = groupVideosIntoColumns(3);

  // Get folder name for display
  const folderName = folderParam ? folderParam.split('/').pop() || folderParam : "All Videos";

  // Check if there are any active generations
  const activeGenerationJobs = queueItems.filter(
    item => item.status === "pending" || item.status === "processing"
  );
  // Also track uploads in progress (completed but not yet uploaded)
  const uploadsInProgress = queueItems.filter(
    item => item.status === "completed" && !item.uploadComplete && jobsInProgress[item.id]
  );
  const hasActiveGenerations = activeGenerationJobs.length > 0 || uploadsInProgress.length > 0;

  // Calculate estimated completion time for ongoing jobs
  const getEstimatedTimeRemaining = () => {
    if (!hasActiveGenerations) return null;
    
    // Find the oldest active job
    const oldestJob = activeGenerationJobs.reduce((oldest, current) => 
      oldest.createdAt < current.createdAt ? oldest : current
    );
    
    // Get progress or estimate it
    const progress = oldestJob.progress || 50;
    
    // Rough estimation based on progress (assuming 2 minutes total generation time)
    const totalEstimatedTime = 120; // seconds
    const elapsedTime = (progress / 100) * totalEstimatedTime;
    const remainingTime = totalEstimatedTime - elapsedTime;
    
    if (remainingTime <= 15) return "less than 15 seconds";
    if (remainingTime <= 30) return "less than 30 seconds";
    if (remainingTime <= 60) return "less than a minute";
    return "about 1-2 minutes";
  };

  // When videos are saved to gallery
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleVideosSaved = () => {
    // Refresh the gallery when videos are saved
    loadVideos(true);
  };

  // Handle video generation
  const handleGenerate = async (settings: {
    prompt: string;
    aspectRatio: string;
    resolution: string;
    duration: string;
    variants: string;
    modality: string;
    analyzeVideo: boolean;
    brandsProtection: string;
    imageModel: string;
    hd: boolean;
    vivid: boolean;
    imageSize: string;
    brandProtectionModel: string;
    moderationThresholds: {
      hate: string;
      selfHarm: string;
      sexual: string;
      violence: string;
    };
    saveImages: boolean;
    imageCache: boolean;
    folder?: string;
    brandsList?: string[];
  }) => {
    // Skip if already generating
    if (isGenerating) return;
    
    setIsGenerating(true);
    
    // Show immediate feedback to the user
    const toastId = toast.loading(`Creating ${settings.variants} video${parseInt(settings.variants) > 1 ? 's' : ''}...`, {
      description: `${settings.aspectRatio}, ${settings.duration} duration - this may take 1-2 minutes`
    });
    
    try {
      let generationPrompt = settings.prompt;
      let brandProtectionApplied = false;
      
      // Apply brand protection if enabled from global settings
      if (imageSettings.settings.brandsProtection !== "off" && imageSettings.settings.brandsList.length > 0) {
        try {
          // Call the brand protection API
          generationPrompt = await protectImagePrompt(
            settings.prompt,
            imageSettings.settings.brandsList,
            imageSettings.settings.brandsProtection
          );
          
          if (generationPrompt !== settings.prompt) {
            brandProtectionApplied = true;
          }
        } catch (error) {
          console.error('Error applying brand protection:', error);
          // Don't show a separate error toast for brand protection - just log and continue
          // The main generation will still proceed with the original prompt
          generationPrompt = settings.prompt;
        }
      }
      
      {
        // For real video generation
        try {
          // Convert string values to numbers for type compatibility
          const videoSettings = {
            resolution: settings.resolution,
            duration: parseInt(settings.duration.replace('s', ''), 10), // Convert "5s" to 5
            variants: parseInt(settings.variants, 10),
            aspectRatio: settings.aspectRatio,
            fps: undefined, // Optional
            brandsProtection: settings.brandsProtection,
            brandsList: settings.brandsList,
            analyzeVideo: settings.analyzeVideo, // Pass the analysis setting
            folder: settings.folder // Pass the folder setting
          };
          
          // Add to queue - this will create the job in the backend
          const jobId = await addToQueue(generationPrompt, videoSettings);
          
          // Track this job to handle its completion properly
          setJobsInProgress(prev => ({
            ...prev,
            [jobId]: true
          }));
          
          // Dismiss the loading toast - the job is now in progress
          toast.dismiss(toastId);
          
          // No need to reset lastCompletedJobId now that we're tracking in jobsInProgress
          
          // Reset generating state
          setIsGenerating(false);
        } catch (error) {
          console.error("Error starting video generation:", error);
          toast.error("Could not connect to the backend API", {
            id: toastId,
            description: "Please try again later"
          });
          setIsGenerating(false);
        }
      }
    } catch (error) {
      console.error("Error during generation:", error);
      setIsGenerating(false);
      toast.error("An error occurred while generating the video", {
        id: toastId,
        description: "Please try again later"
      });
    }
  };
  
  // Handle folder creation
  const handleFolderCreated = (newFolder: string | string[]) => {
    if (Array.isArray(newFolder)) {
      // Update the full folders list
      setFolders(newFolder);
    } else {
      // Single new folder was created
      if (!folders.includes(newFolder)) {
        setFolders(prev => [...prev, newFolder]);
      }
      // Update the selected folder
      setSelectedFolder(newFolder);
    }
  };

  const [fullscreenVideo, setFullscreenVideo] = useState<VideoMetadata | null>(null);
  
  // Function to handle video click - Opens the full-screen modal
  const handleVideoClick = (video: VideoMetadata) => {
    setFullscreenVideo(video);
  };

  // Function to handle video deletion from the detail view
  const handleVideoDeletedFromDetail = (videoId: string) => {
    // Remove the deleted video from the state
    setVideos(prevVideos => prevVideos.filter(video => video.id !== videoId));
    
    // Close the detail view
    setFullscreenVideo(null);
    
    // If we've deleted a video, we might want to load another one to replace it
    if (hasMore && videos.length < limit * 2) {
      loadMoreVideos();
    }
  };

  // Function to handle video move from the detail view
  const handleVideoMovedFromDetail = (videoId: string) => {
    // Only remove the moved video if we're in a folder view
    if (folderParam) {
      // Remove the moved video from the current state
      setVideos(prevVideos => prevVideos.filter(video => video.id !== videoId));
      
      // If we've moved a video, we might want to load another one to replace it
      if (hasMore && videos.length < limit * 2) {
        loadMoreVideos();
      }
    } else {
      // When in "All Videos" view, refresh the gallery to update
      loadVideos(true);
    }
    
    // Close the detail view
    setFullscreenVideo(null);
    
    toast.success("Video moved", {
      description: "The video was moved to another folder"
    });
  };



  return (
    <div className="flex flex-col h-full w-full">
      <PageHeader title={folderParam ? "Album" : "All Videos"} />
      
      <div className="flex-1 w-full h-full overflow-y-auto gallery-container">
        <div className="w-full mx-auto px-10 py-6 pb-40">
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              {folderParam && (
                <Badge variant="outline" className="flex items-center gap-1 px-3 py-1">
                  <FolderIcon className="h-3.5 w-3.5 mr-1" />
                  {folderName}
                </Badge>
              )}
              <span className="text-xs text-muted-foreground">
                {lastRefreshedText}
              </span>
              
              {/* Add active generation indicator */}
              {hasActiveGenerations && (
                <Badge variant="secondary" className="ml-2 bg-primary/20 text-primary animate-pulse">
                  <Loader2 className="h-3 w-3 mr-1.5 animate-spin" />
                  <span className="text-xs">
                    {uploadsInProgress.length > 0 ? (
                      `Uploading ${uploadsInProgress.length} video${uploadsInProgress.length > 1 ? 's' : ''} to gallery...`
                    ) : (
                      `Generating ${activeGenerationJobs.length > 1 ? `${activeGenerationJobs.length} videos` : 'video'} 
                      ${getEstimatedTimeRemaining() ? `(${getEstimatedTimeRemaining()} remaining)` : ''}`
                    )}
                  </span>
                </Badge>
              )}
            </div>
            
            <div className="flex items-center space-x-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="icon"
                      variant={autoPlay ? "outline" : "ghost"}
                      className={`relative h-8 w-8 ${autoPlay ? 'border-primary text-primary' : 'text-muted-foreground'}`}
                      onClick={toggleAutoPlay}
                    >
                      {autoPlay ? (
                        <Video className="h-4 w-4" />
                      ) : (
                        <VideoOff className="h-4 w-4" />
                      )}
                      <span className="sr-only">
                        {autoPlay ? 'Disable auto-play' : 'Enable auto-play'}
                      </span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="left">
                    {autoPlay ? 'Videos auto-play (on)' : 'Videos play on hover (off)'}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>

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
                onClick={() => loadVideos(true)}
                disabled={loading || isRefreshing}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span className="sr-only">Refresh gallery</span>
              </Button>
            </div>
          </div>
          
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {renderSkeletons(12)}
            </div>
          ) : videos.length > 0 ? (
            <div>
              {/* Masonry grid using CSS columns */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {columns.map((column, columnIndex) => (
                  <div key={`column-${columnIndex}`} className="flex flex-col space-y-6">
                    {column.map((video, videoIndex) => {
                      const sampleTags = generateTagsForVideo(video, videoIndex * 3 + columnIndex);
                      
                      // Determine if this should be a large video
                      // For example, every 5th video in the overall sequence
                      const isLarge = (videoIndex * 3 + columnIndex) % 5 === 0;
                      
                      return (
                        <div key={video.name} className="w-full">
                          <VideoCard
                            src={video.src}
                            title={video.title}
                            description={video.description}
                            size={isLarge ? "large" : video.size}
                            className="w-full"
                            tags={sampleTags}
                            id={video.id}
                            blobName={video.name}
                            onDelete={() => handleVideoDeleted(video.name)}
                            onClick={() => handleVideoClick(video)}
                            autoPlay={autoPlay}
                          />
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
              
              {/* Load more button */}
              {hasMore && (
                <div className="mt-8 flex justify-center">
                  <button
                    onClick={loadMoreVideos}
                    disabled={isLoadingMore}
                    className="px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md flex items-center gap-2"
                  >
                    {isLoadingMore ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading...
                      </>
                    ) : (
                      'Load More Videos'
                    )}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-[calc(100vh-20rem)] py-20 text-muted-foreground">
              <FileVideo className="h-16 w-16 mb-4 opacity-20" />
              {folderParam ? (
                <>
                  <p className="text-xl">This album is empty</p>
                  <p className="text-sm mt-2">No videos found in album &quot;{folderName}&quot;</p>
                </>
              ) : (
                <>
                  <p className="text-xl">No videos found in the gallery</p>
                  <p className="text-sm mt-2">Create new videos to get started</p>
                </>
              )}
              <Button 
                onClick={() => loadVideos(true)} 
                variant="outline" 
                className="mt-6"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh Gallery
              </Button>
            </div>
          )}
        </div>

        {/* Video Creation Container - sticky positioned at the bottom */}
        <div className="sticky bottom-0 w-full">
          <VideoOverlay 
            onGenerate={handleGenerate}
            isGenerating={isGenerating}
            folders={folders}
            selectedFolder={selectedFolder}
            onFolderCreated={handleFolderCreated}
          />
        </div>
      </div>

      {/* Video Detail View */}
      <VideoDetailView
        video={fullscreenVideo}
        videos={videos}
        onClose={() => setFullscreenVideo(null)}
        onDelete={handleVideoDeletedFromDetail}
        onMove={handleVideoMovedFromDetail}
        onNavigate={(direction, index) => {
          if (index >= 0 && index < videos.length) {
            setFullscreenVideo(videos[index]);
          }
        }}
      />
    </div>
  );
}

export default function NewVideoPage() {
  return (
    <SlideTransition>
      <Suspense fallback={
        <div className="flex flex-col h-full w-full">
          <PageHeader title="Videos" />
          <div className="flex-1 w-full h-full overflow-y-auto">
            <div className="w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 12 }).map((_, index) => (
                  <Card className="overflow-hidden bg-black p-0 border-0 rounded-xl" key={index}>
                    <AspectRatio ratio={16/9} className="bg-muted">
                      <Skeleton className="h-full w-full rounded-none" />
                    </AspectRatio>
                    <div className="p-4 space-y-2">
                      <Skeleton className="h-4 w-2/3" />
                      <Skeleton className="h-3 w-full" />
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        </div>
      }>
        <NewVideoPageContent />
      </Suspense>
    </SlideTransition>
  );
} 