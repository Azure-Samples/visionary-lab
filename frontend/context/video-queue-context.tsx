"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { VideoGenerationJob, createVideoGenerationJob, getVideoGenerationJob, mapSettingsToApiRequest, downloadThenUploadToGallery, generateVideoFilename, analyzeAndUpdateVideoMetadata, createVideoGenerationWithAnalysis, VideoGenerationWithAnalysisRequest } from "@/services/api";
import { toast } from "sonner";

// Global set to track which generation IDs have already been uploaded
// This survives component re-renders and ensures each generation is only uploaded once
const uploadedGenerations = new Set<string>();

// Global callback registry for refresh notifications
// Components can register callbacks to be notified when uploads complete
type RefreshCallback = () => void;
const refreshCallbacks: RefreshCallback[] = [];

// Register a callback to be called when uploads complete
export function registerGalleryRefreshCallback(callback: RefreshCallback) {
  if (!refreshCallbacks.includes(callback)) {
    refreshCallbacks.push(callback);
    return true;
  }
  return false;
}

// Unregister a callback when component unmounts
export function unregisterGalleryRefreshCallback(callback: RefreshCallback) {
  const index = refreshCallbacks.indexOf(callback);
  if (index !== -1) {
    refreshCallbacks.splice(index, 1);
    return true;
  }
  return false;
}

// Trigger all registered callbacks
function notifyGalleryRefreshNeeded() {
  refreshCallbacks.forEach(callback => {
    try {
      callback();
    } catch (error) {
      console.error('Error in gallery refresh callback:', error);
    }
  });
}

export interface VideoQueueItem {
  id: string;
  prompt: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress?: number;
  createdAt: Date;
  job?: VideoGenerationJob; // Add the actual job data
  uploadComplete?: boolean; // Flag to track when uploads are complete
  uploadStarted?: boolean; // Flag to track when uploads are starting
  analysisSettings?: {
    analyzeVideo: boolean;
  };
  folder?: string; // Store folder information directly in queue item
}

export interface VideoSettings {
  resolution: string;
  duration: number; // This will be parsed from string like "5s"
  variants: number; // This will be parsed from string like "2"
  aspectRatio: string; // Added aspectRatio
  fps?: number;
  brandsProtection?: string; // Add brand protection mode
  brandsList?: string[]; // Add list of brands to protect
  folder?: string; // Add folder information
  analyzeVideo?: boolean; // Add video analysis setting
}

interface VideoQueueContextType {
  queueItems: VideoQueueItem[];
  addToQueue: (prompt: string, settings?: VideoSettings) => Promise<string>; // Returns the ID
  updateQueueItemStatus: (id: string, status: VideoQueueItem["status"], progress?: number) => void;
  removeFromQueue: (id: string) => void;
  getQueueItem: (id: string) => VideoQueueItem | undefined;
}

const VideoQueueContext = createContext<VideoQueueContextType | undefined>(undefined);

export function VideoQueueProvider({ children }: { children: React.ReactNode }) {
  const [queueItems, setQueueItems] = useState<VideoQueueItem[]>([]);
  const [isClient, setIsClient] = useState(false);

  // This effect runs once on client-side to mark that we're now on the client
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Poll for job status updates every 5 seconds
  useEffect(() => {
    // Skip processing during server-side rendering or before client hydration is complete
    if (!isClient) return;

    // Create a polling function to check job status
    const pollJobStatus = async () => {
      // Clone the queue items to avoid mutating state directly
      const updatedItems = [...queueItems];
      let hasUpdates = false;
      let uploadCompleted = false;

      // Check each item with a backend job
      for (let i = 0; i < updatedItems.length; i++) {
        const item = updatedItems[i];
        
        // Skip items without a job or already completed/failed
        if (!item.job || item.status === "completed" || item.status === "failed") {
          continue;
        }
        
        // Skip items where uploads are already in progress or complete
        if (item.uploadStarted || item.uploadComplete) {
          continue;
        }
        
        try {
          // Get latest job status from API
          const updatedJob = await getVideoGenerationJob(item.job.id);
          
          // Update job data
          updatedItems[i] = {
            ...item,
            job: updatedJob,
          };
          
          // Update status based on job status
          if (updatedJob.status === "succeeded") {
            updatedItems[i].status = "completed";
            updatedItems[i].progress = 100;
            hasUpdates = true;

            // Handle uploading multiple generations if they exist
            if (updatedJob.generations && updatedJob.generations.length > 0) {
              // Handle each generation
              const uploadPromises = updatedJob.generations
                .filter(generation => !uploadedGenerations.has(generation.id)) // Only process generations not already uploaded
                .map(async (generation: { id: string; prompt?: string }, index: number) => {
                  // Mark this generation as being processed to prevent duplicate uploads
                  uploadedGenerations.add(generation.id);
                  
                  const fileName = generateVideoFilename(generation.prompt || item.prompt, generation.id);
                  
                  // Define metadata for the uploaded asset
                  const metadata = {
                    prompt: generation.prompt || item.prompt,
                    sourceJobId: item.job?.id || "unknown_job",
                    generationId: generation.id,
                    variantIndex: (index + 1).toString(),
                    totalVariants: updatedJob.generations?.length.toString() || "0",
                    originalAspectRatio: item.job?.width && item.job?.height ? `${item.job.width}x${item.job.height}` : "unknown",
                    originalDuration: item.job?.n_seconds ? `${item.job.n_seconds}s` : "unknown",
                    folder: item.job?.metadata?.folder || "root"
                  };

                  // Pass folder information to the download/upload function if available
                  // Use folder from queue item first, then fall back to job metadata
                  const folder = item.folder || item.job?.metadata?.folder || undefined;
                  
                  try {
                    await downloadThenUploadToGallery(generation.id, fileName, metadata, folder);
                    
                    // Analyze the video if analysis is enabled for this queue item
                    const queueItem = queueItems.find(item => item.job?.id === updatedJob.id);
                    const analysisSettings = queueItem?.analysisSettings;
                    
                    if (analysisSettings?.analyzeVideo) {
                      try {
                        // Wait 10 seconds for Azure Blob Storage to propagate the uploaded video
                        await new Promise(resolve => setTimeout(resolve, 10000));
                        
                        const analysisResult = await analyzeAndUpdateVideoMetadata(fileName);
                        
                        // Don't show individual analysis toasts - we'll show a consolidated one later
                                              } catch (analysisError) {
                          console.error(`Video analysis failed for ${generation.id}:`, analysisError);
                          // Don't show individual analysis error toasts - log the error for debugging
                        }
                    }
                    
                    return true;
                  } catch (error) {
                    console.error(`Error uploading generation ${generation.id}:`, error);
                    return false;
                  }
                });
              
              if (uploadPromises.length > 0) {
                // Use a loading toast that transforms into success/error
                const uploadToastId = toast.loading(`Uploading ${uploadPromises.length} video${uploadPromises.length > 1 ? 's' : ''} to gallery...`);
                
                try {
                  // Wait for all uploads to complete
                  const results = await Promise.all(uploadPromises);
                  const successCount = results.filter(Boolean).length;
                  
                  if (successCount > 0) {
                    // Check if analysis was enabled for this job
                    const queueItem = queueItems.find(item => item.job?.id === updatedJob.id);
                    const analysisEnabled = queueItem?.analysisSettings?.analyzeVideo;
                    
                    const description = analysisEnabled 
                      ? `${successCount} video${successCount > 1 ? 's' : ''} uploaded with AI analysis`
                      : `${successCount} video${successCount > 1 ? 's' : ''} ready in your gallery`;
                    
                    toast.success(`Videos uploaded successfully`, {
                      id: uploadToastId,
                      description,
                      duration: 5000
                    });
                    
                    // Set flag to notify galleries about new content
                    uploadCompleted = true;
                  }
                  
                  if (successCount < uploadPromises.length) {
                    toast.error(`${uploadPromises.length - successCount} video${uploadPromises.length - successCount > 1 ? 's' : ''} failed to upload`, {
                      id: uploadToastId
                    });
                  }
                } catch (uploadError) {
                  console.error(`Error handling uploads:`, uploadError);
                  toast.error(`Some videos failed to upload`, {
                    id: uploadToastId
                  });
                }
              } else {
                console.log(`All generations for job ${updatedJob.id} were already uploaded`);
              }
              
              // Mark this item with a special "uploaded" flag so the UI knows everything is ready
              updatedItems[i].uploadComplete = true;
            } else {
              console.log(`Job ${updatedJob.id} completed but no generations were found`);
              toast.info(`Job completed but no videos were generated.`);
              updatedItems[i].uploadComplete = true;
            }

          } else if (updatedJob.status === "failed") {
            updatedItems[i].status = "failed";
            hasUpdates = true;
          } else if (updatedJob.status === "running" || updatedJob.status === "processing") {
            if (item.status !== "processing") {
              updatedItems[i].status = "processing";
              hasUpdates = true;
            }
            
            // Estimate progress based on time elapsed (assuming max 2 minutes processing time)
            if (updatedJob.created_at) {
              const elapsedSeconds = (Date.now() / 1000) - updatedJob.created_at;
              const estimatedProgress = Math.min(95, (elapsedSeconds / 120) * 100);
              
              if (Math.abs((item.progress || 0) - estimatedProgress) > 5) {
                updatedItems[i].progress = estimatedProgress;
                hasUpdates = true;
              }
            }
          }
        } catch (error) {
          console.error(`Error polling job ${item.job.id}:`, error);
          
          // Don't mark as failed immediately for timeout/connection errors
          // Instead, just skip this update and try again on the next poll
          
          // Only update status to failed if it's a clear API failure (not a connection issue)
          if (error instanceof Error && 
              !(error.message.includes("timeout") || 
                error.message.includes("network") || 
                error.message.includes("Connection") ||
                error.message.includes("Max retries exceeded"))) {
            updatedItems[i].status = "failed";
            hasUpdates = true;
          }
        }
      }
      
      // Update state if there were any changes
      if (hasUpdates) {
        setQueueItems(updatedItems);
      }
      
      // If any uploads were completed, notify all registered gallery components
      if (uploadCompleted) {
        // Slight delay to ensure uploads are fully registered in the backend
        setTimeout(() => {
          notifyGalleryRefreshNeeded();
        }, 500);
      }
    };
    
    // Poll every 5 seconds instead of 2
    const intervalId = setInterval(pollJobStatus, 5000);
    
    // Run once immediately
    pollJobStatus();
    
    return () => clearInterval(intervalId);
  }, [queueItems, isClient]);

  const addToQueue = async (prompt: string, settings?: VideoSettings): Promise<string> => {
    // Ensure we're on the client side
    if (!isClient) return "";
    
    try {
      // Generate a temporary local ID for immediate UI feedback
      const tempId = `temp-${Date.now()}`;
      
      // Create initial queue item
      const newItem: VideoQueueItem = {
        id: tempId,
        prompt,
        status: "pending",
        createdAt: new Date(),
        analysisSettings: settings ? {
          analyzeVideo: settings.analyzeVideo || false
        } : undefined,
        folder: settings?.folder, // Store folder directly in queue item
      };
      
      // Update queue with pending item
      setQueueItems(prev => [...prev, newItem]);
      
      // If settings are provided, create a real backend job
      if (settings) {
        const apiRequest = mapSettingsToApiRequest({
          prompt,
          resolution: settings.resolution,
          duration: settings.duration.toString(), // Convert number to string
          variants: settings.variants.toString(), // Convert number to string
          aspectRatio: settings.aspectRatio, // Pass aspectRatio
          fps: settings.fps
        });
        
        // Add folder information to the job metadata
        const jobMetadata: Record<string, string> = {};
        if (settings.folder) {
          jobMetadata.folder = settings.folder;
        }
        if (settings.brandsProtection && settings.brandsProtection !== "off") {
          jobMetadata.brandsProtection = settings.brandsProtection;
        }
        if (settings.brandsList && settings.brandsList.length > 0) {
          jobMetadata.brandsList = JSON.stringify(settings.brandsList);
        }
        if (settings.analyzeVideo !== undefined) {
          jobMetadata.analyzeVideo = settings.analyzeVideo.toString();
        }
        
        // Check if we should use the unified endpoint with analysis
        if (settings.analyzeVideo) {
          // Use the unified endpoint that handles generation + analysis atomically
          const unifiedRequest: VideoGenerationWithAnalysisRequest = {
            ...apiRequest,
            analyze_video: true,
            metadata: jobMetadata
          };
          
          try {
            const unifiedResponse = await createVideoGenerationWithAnalysis(unifiedRequest);
            const job = unifiedResponse.job;
            
            // Don't show immediate success toast for unified endpoint
            // The regular polling mechanism will handle the final success notification
            
            // Update the queue item with the completed job
            setQueueItems(prev => 
              prev.map(item => 
                item.id === tempId
                  ? { 
                      ...item, 
                      id: job.id, 
                      job,
                      status: "completed",
                      progress: 100,
                      uploadComplete: true, // Mark as complete since unified endpoint handles everything
                      folder: item.folder // Preserve folder information
                    }
                  : item
              )
            );
            
            return job.id;
          } catch (error) {
            console.error("Unified endpoint failed, falling back to traditional approach:", error);
            toast.error("Unified generation failed, trying traditional approach...");
            
            // Fall back to the traditional approach
            const job = await createVideoGenerationJob({
              ...apiRequest,
              metadata: jobMetadata
            });
            
            // Update the queue item with the real job ID and data
            setQueueItems(prev => 
              prev.map(item => 
                item.id === tempId
                  ? { ...item, id: job.id, job, folder: item.folder } // Preserve folder information
                  : item
              )
            );
            
            return job.id;
          }
        } else {
          // Use traditional endpoint for non-analysis jobs
          const job = await createVideoGenerationJob({
            ...apiRequest,
            metadata: jobMetadata
          });
          
          // Update the queue item with the real job ID and data
          setQueueItems(prev => 
            prev.map(item => 
              item.id === tempId
                ? { ...item, id: job.id, job, folder: item.folder } // Preserve folder information
                : item
            )
          );
          
                     return job.id;
         }
      }
      
      return tempId;
    } catch (error) {
      console.error("Error adding to queue:", error);
      return "";
    }
  };

  const updateQueueItemStatus = (
    id: string, 
    status: VideoQueueItem["status"], 
    progress?: number
  ) => {
    setQueueItems(prev => 
      prev.map(item => 
        item.id === id ? { ...item, status, ...(progress !== undefined ? { progress } : {}) } : item
      )
    );
  };

  const removeFromQueue = (id: string) => {
    setQueueItems(prev => prev.filter(item => item.id !== id));
  };
  
  const getQueueItem = (id: string) => {
    return queueItems.find(item => item.id === id);
  };

  return (
    <VideoQueueContext.Provider
      value={{
        queueItems,
        addToQueue,
        updateQueueItemStatus,
        removeFromQueue,
        getQueueItem,
      }}
    >
      {children}
    </VideoQueueContext.Provider>
  );
}

export function useVideoQueue() {
  const context = useContext(VideoQueueContext);
  if (context === undefined) {
    throw new Error("useVideoQueue must be used within a VideoQueueProvider");
  }
  return context;
} 