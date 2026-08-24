import React from 'react';
import { useVideoQueue, type VideoQueueItem } from '../../context/video-queue-context';
import { generateVideoFilename, getVideoDownloadUrl } from '../../services/api';
import { toast } from 'sonner';
import { VideoGenerationProgress } from './VideoGenerationProgress';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';

export interface VideoSettings {
  resolution: string;
  duration: number;
  fps: number;
  variants: number;
}

export function VideoQueue() {
  // The useVideoQueue hook is now re-exported from our standalone implementation
  // This ensures it will use the context if available
  const { queueItems, removeFromQueue } = useVideoQueue();

  // Filter videos by status
  const activeVideos = queueItems.filter(
    video => video.status === 'pending' || video.status === 'processing'
  );
  const completedVideos = queueItems.filter(video => video.status === 'completed');
  const failedVideos = queueItems.filter(video => video.status === 'failed');

  // Handle download button click
  const handleDownload = (video: VideoQueueItem) => {
    try {
      const generation = video.job?.generations?.[0];
      if (!generation) {
        throw new Error('No generated video is available');
      }

      const fileName = generateVideoFilename(
        generation.prompt || video.prompt,
        generation.id,
      );
      const link = document.createElement('a');
      link.href = getVideoDownloadUrl(generation.id, fileName);
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('Download started', {
        description: 'Your video is being downloaded',
      });
    } catch (error) {
      toast.error('Download failed', {
        description: error instanceof Error ? error.message : 'An unknown error occurred',
      });
    }
  };

  // Handle cancel/remove button click
  const handleCancel = (video: VideoQueueItem) => {
    removeFromQueue(video.id);
    
    toast.success('Generation cancelled', {
      description: `Video "${video.prompt.substring(0, 20)}${video.prompt.length > 20 ? '...' : ''}" removed from queue`,
    });
  };

  if (queueItems.length === 0) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Video Queue</CardTitle>
          <CardDescription>No videos in queue</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-32 text-muted-foreground">
          Videos you generate will appear here
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Video Queue</CardTitle>
        <CardDescription>
          {queueItems.length} video{queueItems.length !== 1 ? 's' : ''} in queue
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="active" className="w-full">
          <TabsList className="mb-4">
            <TabsTrigger value="active">
              In Progress ({activeVideos.length})
            </TabsTrigger>
            <TabsTrigger value="completed">
              Completed ({completedVideos.length})
            </TabsTrigger>
            <TabsTrigger value="failed">
              Failed ({failedVideos.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="active">
            {activeVideos.length > 0 ? (
              <div className="space-y-4">
                {activeVideos.map((video) => (
                  <VideoGenerationProgress
                    key={video.id}
                    queueItem={video}
                    onCancel={() => handleCancel(video)}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No videos in progress
              </div>
            )}
          </TabsContent>

          <TabsContent value="completed">
            {completedVideos.length > 0 ? (
              <div className="space-y-4">
                {completedVideos.map((video) => (
                  <VideoGenerationProgress
                    key={video.id}
                    queueItem={video}
                    onDownload={() => handleDownload(video)}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No completed videos
              </div>
            )}
          </TabsContent>

          <TabsContent value="failed">
            {failedVideos.length > 0 ? (
              <div className="space-y-4">
                {failedVideos.map((video) => (
                  <VideoGenerationProgress
                    key={video.id}
                    queueItem={video}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No failed videos
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
