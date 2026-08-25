'use client';

import React, { useState, useRef, useCallback } from 'react';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { UploadIcon, ImageIcon, AlertCircleIcon, FileIcon, XIcon } from 'lucide-react';
import { Progress } from "@/components/ui/progress";
import { Badge } from '@/components/ui/badge';

interface ImageUploaderProps {
  onImageUpload: (file: File) => void;
}

// Maximum GPT-Image-2 source image size in bytes (50 MB).
const MAX_FILE_SIZE = 50 * 1024 * 1024;
// Allowed file types
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];

export default function ImageUploader({ onImageUpload }: ImageUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Clean up the preview URL when component unmounts
  React.useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  // Process the uploaded file
  const processFile = useCallback((file: File) => {
    setError(null);
    setIsLoading(true);
    
    // Validate the file
    const validateFile = (file: File): boolean => {
      // Check file type
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError(`Unsupported file type. Please upload PNG, JPEG, or WebP images.`);
        return false;
      }

      // Check file size
      if (file.size >= MAX_FILE_SIZE) {
        setError(`File is too large. Maximum size is 50MB.`);
        return false;
      }

      return true;
    };
    
    if (validateFile(file)) {
      // Simulate progress for better user experience
      const startTime = Date.now();
      const duration = 1500; // milliseconds for simulation
      
      const progressInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min((elapsed / duration) * 100, 99);
        setUploadProgress(progress);
        
        if (progress >= 99) {
          clearInterval(progressInterval);
        }
      }, 50);
      
      // Create a preview
      const objectUrl = URL.createObjectURL(file);
      
      // Clean up previous preview if exists
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      
      // Simulate a delay for the preview to load
      setTimeout(() => {
        setPreviewUrl(objectUrl);
        setUploadProgress(100);
        setIsLoading(false);
        onImageUpload(file);
        clearInterval(progressInterval);
      }, 1000);
    } else {
      setIsLoading(false);
    }
  }, [onImageUpload, previewUrl]);

  // Handle file input change
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      processFile(file);
    }
  };

  // Handle file drop
  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    
    const file = event.dataTransfer.files?.[0];
    if (file) {
      processFile(file);
    }
  }, [processFile]);

  // Handle drag events
  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Trigger file selection dialog
  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="w-full space-y-4">
      <Card
        className={`border-2 border-dashed p-6 text-center ${
          isDragging 
            ? 'border-primary bg-primary/5' 
            : isLoading 
              ? 'border-muted-foreground/25 bg-muted/10' 
              : 'border-muted-foreground/25'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex flex-col items-center justify-center space-y-4 py-6">
          {isLoading && (
            <div className="flex flex-col items-center space-y-4 w-full max-w-md">
              <div className="rounded-full bg-primary/10 p-4">
                <FileIcon className="h-8 w-8 text-primary animate-pulse" />
              </div>
              <div className="w-full">
                <div className="flex justify-between text-sm mb-1">
                  <span>Uploading image...</span>
                  <span>{Math.round(uploadProgress)}%</span>
                </div>
                <Progress value={uploadProgress} className="w-full" />
              </div>
            </div>
          )}
          
          {previewUrl && !isLoading ? (
            <div className="relative max-h-64 max-w-full">
              <div className="relative h-64 w-full">
                <Image 
                  src={previewUrl} 
                  alt="Preview" 
                  fill
                  className="object-contain rounded-md shadow-md"
                  sizes="(max-width: 768px) 100vw, 50vw"
                  unoptimized
                />
              </div>
              <Button
                variant="outline"
                size="icon"
                className="absolute top-2 right-2 bg-background/80 backdrop-blur-sm hover:bg-background"
                onClick={() => {
                  if (previewUrl) {
                    URL.revokeObjectURL(previewUrl);
                  }
                  setPreviewUrl(null);
                  setError(null);
                  if (fileInputRef.current) {
                    fileInputRef.current.value = '';
                  }
                }}
              >
                <XIcon className="h-4 w-4" />
              </Button>
            </div>
          ) : !isLoading ? (
            <>
              <div className="rounded-full bg-primary/10 p-4">
                <ImageIcon className="h-8 w-8 text-primary" />
              </div>
              <div>
                <p className="text-lg font-medium">Drag &amp; Drop your image here</p>
                <p className="text-sm text-muted-foreground mt-1">PNG, JPEG, or WebP. Max 50MB.</p>
              </div>
              <div className="mt-4">
                <Button onClick={handleButtonClick} className="gap-2">
                  <UploadIcon className="h-4 w-4" />
                  Select Image
                </Button>
              </div>
            </>
          ) : null}
          
          <Input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/webp"
            className="hidden"
            onChange={handleFileChange}
            disabled={isLoading}
          />
        </div>
      </Card>
      
      {error && (
        <div className="flex items-center gap-2 text-destructive text-sm mt-2 p-2 bg-destructive/10 rounded border border-destructive/20">
          <AlertCircleIcon className="h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}
      
      {previewUrl && !isLoading && (
        <div className="flex justify-center gap-2 flex-wrap">
          <Badge variant="outline" className="py-1.5">
            Ready to proceed
          </Badge>
          <Badge variant="outline" className="py-1.5">
            Click &quot;Continue&quot; when ready
          </Badge>
        </div>
      )}
    </div>
  );
} 
