"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { VideoCard } from "@/components/VideoCard";
import { PageHeader } from "@/components/page-header";
import { fetchVideos, VideoMetadata } from "@/utils/gallery-utils";
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
import { SlideTransition } from "@/components/ui/page-transition";

// Component that safely uses useSearchParams
function SearchParamsWrapper({ onFolderChange }: { onFolderChange: (folder: string | null) => void }) {
  const searchParams = useSearchParams();
  const folderParam = searchParams.get('folder');
  
  // Update parent component when folder changes
  useEffect(() => {
    onFolderChange(folderParam);
  }, [folderParam, onFolderChange]);
  
  return null;
}

export default function GalleryPage() {
  const [folderParam, setFolderParam] = useState<string | null>(null);
  
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
  const limit = 50;

  const loadVideos = useCallback(async (resetVideos = true, isAutoRefresh = false) => {
    if (resetVideos) {
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
      const fetchedVideos = await fetchVideos(limit, resetVideos ? 0 : offset, folderParam || undefined);
      
      if (resetVideos) {
        setVideos(fetchedVideos);
        
        // Update last refreshed time
        const now = new Date();
        setLastRefreshed(now);
        setLastRefreshedText(`Last refreshed ${formatDistanceToNow(now, { addSuffix: true })}`);
      } else {
        setVideos(prevVideos => [...prevVideos, ...fetchedVideos]);
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
  }, [folderParam, limit, offset]);

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
      const interval = setInterval(() => {
        loadVideos(true, true);
      }, 30000); // 30 seconds
      
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
  }, [autoRefresh, refreshInterval, loadVideos]);

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

  // When folder parameter changes, reload videos
  useEffect(() => {
    loadVideos(true, false);
  }, [folderParam, loadVideos]);

  // Initial load
  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

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
  const generateTagsForVideo = (video: VideoMetadata): string[] => {
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



  return (
    <SlideTransition>
      <div className="flex flex-col h-full">
        <PageHeader title={folderParam ? `Videos in ${folderParam}` : "All Videos"}>
          <div className="flex items-center">
            {folderParam && (
              <Badge variant="outline" className="mr-2 text-xs">
                <FolderIcon className="w-3 h-3 mr-1" />
                {folderParam}
              </Badge>
            )}

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => loadVideos(true)}
                    disabled={isRefreshing || loading}
                    className="mr-2"
                  >
                    <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Refresh videos</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={autoRefresh ? "default" : "outline"}
                    size="icon"
                    onClick={toggleAutoRefresh}
                    className="mr-2"
                  >
                    <Clock className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{autoRefresh ? "Auto-refresh ON" : "Auto-refresh OFF"}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={autoPlay ? "default" : "outline"}
                    size="icon"
                    onClick={toggleAutoPlay}
                  >
                    {autoPlay ? <Video className="h-4 w-4" /> : <VideoOff className="h-4 w-4" />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{autoPlay ? "Auto-play ON" : "Auto-play OFF"}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </PageHeader>

        <div className="text-xs text-muted-foreground px-4 pb-2">
          {lastRefreshedText}
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24">
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                <Suspense fallback={null}>
                  <SearchParamsWrapper onFolderChange={setFolderParam} />
                </Suspense>

                {loading ? (
                  renderSkeletons(12)
                ) : videos.length > 0 ? (
                  videos.map((video) => (
                    <VideoCard
                      key={video.name}
                      src={video.src}
                      title={video.title}
                      description={video.description}
                      blobName={video.name}
                      onDelete={() => handleVideoDeleted(video.name)}
                      autoPlay={autoPlay}
                      tags={generateTagsForVideo(video)}
                    />
                  ))
                ) : (
                  <div className="col-span-full flex flex-col items-center justify-center py-16 text-center bg-muted rounded-xl">
                    <FileVideo className="h-16 w-16 text-muted-foreground mb-6" />
                    <h3 className="text-xl font-medium mb-2">No Videos Found</h3>
                    <p className="text-muted-foreground max-w-md">
                      There are no videos in this location. You can create a new video using the video generation tool.
                    </p>
                  </div>
                )}
              </div>

              {hasMore && !loading && (
                <div className="flex justify-center mt-8">
                  <Button
                    variant="outline"
                    onClick={loadMoreVideos}
                    disabled={isLoadingMore}
                    className="w-48"
                  >
                    {isLoadingMore ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Loading
                      </>
                    ) : (
                      "Load More"
                    )}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </SlideTransition>
  );
} 