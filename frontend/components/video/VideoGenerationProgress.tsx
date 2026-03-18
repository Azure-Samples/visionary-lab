import React from 'react';
import { Progress } from '../ui/progress';
import { Button } from '../ui/button';
import { VideoQueueItem } from '../../hooks/useVideoQueue';
import { Clock, CheckCircle, AlertCircle, Film } from 'lucide-react';

interface VideoGenerationProgressProps {
  queueItem: VideoQueueItem;
  onDownload?: () => void;
  onCancel?: () => void;
}

export function VideoGenerationProgress({ 
  queueItem, 
  onDownload, 
  onCancel 
}: VideoGenerationProgressProps) {
  const { status, progress, prompt } = queueItem;
  
  // Get appropriate status icon
  function StatusIcon() {
    switch (status) {
      case 'pending':
        return <Clock className="h-5 w-5 text-yellow-500" />;
      case 'processing':
        return <Film className="h-5 w-5 text-blue-500 animate-pulse" />;
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      default:
        return null;
    }
  }

  // Get status message
  function getStatusMessage(): string {
    switch (status) {
      case 'pending':
        return 'Waiting in queue...';
      case 'processing':
        return `Generating video: ${progress}%`;
      case 'completed':
        return 'Video generation completed';
      case 'failed':
        return 'Video generation failed';
      default:
        return '';
    }
  }

  // Status-specific styles and text
  function getStatusDetails(): {
    label: string;
    description: string;
    color: string;
  } {
    switch (status) {
      case 'pending':
        return {
          label: 'Pending',
          description: 'Waiting to start processing',
          color: 'bg-muted',
        };
      case 'processing':
        return {
          label: 'Processing',
          description: `Generating video (${Math.round(progress)}%)`,
          color: 'bg-primary',
        };
      case 'completed':
        return {
          label: 'Completed',
          description: 'Video generation finished',
          color: 'bg-green-500',
        };
      case 'failed':
        return {
          label: 'Failed',
          description: 'Video generation failed',
          color: 'bg-destructive',
        };
      default:
        return {
          label: 'Unknown',
          description: 'Unknown status',
          color: 'bg-muted',
        };
    }
  }

  const statusDetails = getStatusDetails();
  const progressValue =
    status === 'completed' || status === 'failed' ? 100 : progress;

  return (
    <div className="border rounded-lg p-4 mb-4 bg-card">
      <div className="flex items-start gap-3 mb-3">
        <div className="mt-1">
          <StatusIcon />
        </div>
        <div className="flex-1">
          <h3 className="font-medium text-sm line-clamp-1 mb-1">{prompt}</h3>
          <div className="text-xs text-muted-foreground mb-2">
            {getStatusMessage()}
          </div>
          
          {/* Progress bar */}
          <Progress 
            value={progressValue}
            className={status === 'failed' ? 'bg-destructive/30' : ''}
            indicatorClassName={statusDetails.color}
          />
          
          {/* Metadata display if available */}
          {queueItem.metadata && (
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground mb-3">
              {queueItem.metadata.width && queueItem.metadata.height && (
                <span>{queueItem.metadata.width}×{queueItem.metadata.height}</span>
              )}
              {queueItem.metadata.duration && (
                <span>{queueItem.metadata.duration}s</span>
              )}
              {queueItem.metadata.fps && (
                <span>{queueItem.metadata.fps} FPS</span>
              )}
            </div>
          )}
          
          {/* Action buttons */}
          <div className="flex gap-2 mt-2">
            {status === 'completed' && onDownload && (
              <Button size="sm" onClick={onDownload}>
                Download
              </Button>
            )}
            
            {(status === 'pending' || status === 'processing') && onCancel && (
              <Button size="sm" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 
