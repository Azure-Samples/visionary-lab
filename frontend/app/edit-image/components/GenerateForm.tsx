'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Wand2Icon, RotateCwIcon } from 'lucide-react';
import { toast } from "sonner";
import { createDebugMask } from './createDebugMask';

interface GenerateFormProps {
  originalImage: {
    file: File;
    url: string;
    width: number;
    height: number;
  };
  maskCanvas: HTMLCanvasElement;
  onSubmit: (formData: FormData) => Promise<void>;
}

export default function GenerateForm({
  originalImage,
  maskCanvas,
  onSubmit
}: GenerateFormProps) {
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [model] = useState('gpt-image-1');
  const [quality, setQuality] = useState('auto');
  const [size] = useState('auto');
  const [outputFormat, setOutputFormat] = useState('png');
  const [showPromptIdeas, setShowPromptIdeas] = useState(false);

  // Create the debug mask URL on component mount
  useEffect(() => {
    // Create a debug version of the mask to display
    createDebugMask(maskCanvas, originalImage.width, originalImage.height);
  }, [maskCanvas, originalImage.width, originalImage.height]);

  // Convert the mask to proper format for API (transparent where edits should happen)
  const getProperMaskForAPI = (): HTMLCanvasElement => {
    // Create a properly formatted mask with transparency and alpha channel
    const properMaskCanvas = document.createElement('canvas');
    properMaskCanvas.width = originalImage.width;
    properMaskCanvas.height = originalImage.height;
    
    // Get the context for the canvas
    const ctx = properMaskCanvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) {
      console.error("Could not get canvas context");
      return properMaskCanvas;
    }
    
    // Use the same approach as in createDebugMask to ensure consistency
    // Fill the canvas with opaque black (areas to preserve)
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, properMaskCanvas.width, properMaskCanvas.height);
    
    // Get the mask drawing
    const maskCtx = maskCanvas.getContext('2d', { willReadFrequently: true });
    if (!maskCtx) {
      console.error("Could not get mask canvas context");
      return properMaskCanvas;
    }
    
    // Get original mask data
    const originalMaskData = maskCtx.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
    
    // Create a new ImageData for the scaled mask
    const scaledMaskData = ctx.createImageData(originalImage.width, originalImage.height);
    
    // Calculate scale factors
    const scaleX = originalImage.width / maskCanvas.width;
    const scaleY = originalImage.height / maskCanvas.height;
    
    // Initialize all pixels as opaque black (areas to preserve)
    for (let i = 0; i < scaledMaskData.data.length; i += 4) {
      scaledMaskData.data[i] = 0;       // R = 0
      scaledMaskData.data[i + 1] = 0;   // G = 0
      scaledMaskData.data[i + 2] = 0;   // B = 0
      scaledMaskData.data[i + 3] = 255; // Alpha = 255 (fully opaque)
    }
    
    // For each pixel in the target image
    let transparentPixels = 0;
    for (let y = 0; y < originalImage.height; y++) {
      for (let x = 0; x < originalImage.width; x++) {
        // Find the corresponding pixel in the source mask
        const sourceX = Math.floor(x / scaleX);
        const sourceY = Math.floor(y / scaleY);
        
        // Make sure we're within bounds of the source
        if (sourceX >= 0 && sourceX < maskCanvas.width && 
            sourceY >= 0 && sourceY < maskCanvas.height) {
          
          // Get index in source data
          const sourceIndex = (sourceY * maskCanvas.width + sourceX) * 4;
          
          // Get index in target data
          const targetIndex = (y * originalImage.width + x) * 4;
          
          // If source pixel has alpha > 0 (was drawn on), make target pixel transparent
          if (originalMaskData.data[sourceIndex + 3] > 0) {
            // Make pixel transparent (area to edit)
            scaledMaskData.data[targetIndex + 3] = 0; // Alpha = 0 (transparent)
            transparentPixels++;
          }
        }
      }
    }
    
    // Put the modified data back
    ctx.putImageData(scaledMaskData, 0, 0);
    
    if (transparentPixels === 0) {
      console.error("ERROR: Final mask has no transparent pixels! API will not edit any part of the image.");
    }
    return properMaskCanvas;
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!prompt.trim()) {
      toast.error("Please provide a prompt", {
        description: "Describe what you want to generate in the masked areas"
      });
      return;
    }
    
    setIsLoading(true);
    
    try {
      // Create form data for submission
      const formData = new FormData();
      formData.append('prompt', prompt);
      formData.append('model', model);
      formData.append('n', '1');
      formData.append('size', size);
      formData.append('quality', quality);
      formData.append('output_format', outputFormat);
      
      // Check if the original image is too large and needs optimization
      if (originalImage.file.size > 5 * 1024 * 1024) { // If larger than 5MB
        
        // Create a canvas to resize the image
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        if (ctx) {
          // Create an image element to load the file
          const img = new Image();
          
          // Set up a promise to handle the image loading
          await new Promise<void>((resolve, reject) => {
            img.onload = () => {
              // Calculate a smaller size while preserving aspect ratio
              const MAX_WIDTH = 1536;
              const MAX_HEIGHT = 1536;
              let width = img.width;
              let height = img.height;
              
              if (width > MAX_WIDTH || height > MAX_HEIGHT) {
                if (width > height) {
                  height = Math.round(height * (MAX_WIDTH / width));
                  width = MAX_WIDTH;
                } else {
                  width = Math.round(width * (MAX_HEIGHT / height));
                  height = MAX_HEIGHT;
                }
              }
              
              canvas.width = width;
              canvas.height = height;
              
              // Draw the image to the canvas at the new size
              ctx.drawImage(img, 0, 0, width, height);
              
              // Convert the canvas to a blob
              canvas.toBlob((blob) => {
                if (blob) {
                  // Create a new File from the blob
                  const optimizedFile = new File([blob], originalImage.file.name, { 
                    type: 'image/jpeg',
                    lastModified: Date.now()
                  });
                  

                  
                  // Add to the form data
                  formData.append('image', optimizedFile);
                  resolve();
                } else {
                  reject(new Error('Failed to optimize image'));
                }
              }, 'image/jpeg', 0.85);
            };
            
            img.onerror = () => reject(new Error('Failed to load image for optimization'));
            
            // Set the source of the image to the original file
            img.src = URL.createObjectURL(originalImage.file);
          });
        } else {
          // If context fails, use original
          formData.append('image', originalImage.file);
        }
      } else {
        // Append the original image if it's not too large
        formData.append('image', originalImage.file);
      }
      
      // Convert and append the mask
      const properMask = getProperMaskForAPI();
      properMask.toBlob(async (blob) => {
        try {
          if (!blob) {
            throw new Error('Failed to convert mask to blob');
          }
          
          // Create a FormData object
          const formData = new FormData();
          formData.append('prompt', prompt);
          formData.append('image', originalImage.file);
          formData.append('mask', blob);
          formData.append('model', model);
          formData.append('quality', quality);
          formData.append('size', size);
          formData.append('output_format', outputFormat);
          
          // Submit the form data
          await onSubmit(formData);
          
          console.log('Image edit request submitted successfully');
        } catch (error) {
          console.error('Error processing mask:', error);
          throw error;
        } finally {
          setIsLoading(false);
        }
      }, 'image/png', 0.8);
    } catch (error) {
      console.error('Error submitting form:', error);
      setIsLoading(false);
      toast.error("Error submitting form", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
    }
  };
  
  const handleUsePromptIdea = (idea: string) => {
    setPrompt(idea);
    setShowPromptIdeas(false);
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <div className="flex justify-between items-center">
            <Label htmlFor="prompt" className="text-base font-medium">
              Describe what you want in the edited areas
            </Label>
          </div>
          
          <div className="relative mt-1.5">
            <Textarea
              id="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Example: A beautiful mountain landscape with snow-capped peaks and a clear blue sky"
              className="min-h-[100px] resize-y"
              disabled={isLoading}
            />
          </div>
          
          {showPromptIdeas && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <Button 
                type="button" 
                variant="outline" 
                size="sm" 
                onClick={() => handleUsePromptIdea("A serene mountain landscape with snow-capped peaks")}
              >
                Mountain landscape
              </Button>
              <Button 
                type="button" 
                variant="outline" 
                size="sm" 
                className="text-xs h-auto py-1.5 justify-start"
                onClick={() => handleUsePromptIdea("A tropical beach with palm trees and turquoise water")}
              >
                Tropical beach
              </Button>
              <Button 
                type="button" 
                variant="outline" 
                size="sm" 
                className="text-xs h-auto py-1.5 justify-start"
                onClick={() => handleUsePromptIdea("A futuristic cityscape with flying cars and neon lights")}
              >
                Futuristic city
              </Button>
              <Button 
                type="button" 
                variant="outline" 
                size="sm" 
                className="text-xs h-auto py-1.5 justify-start"
                onClick={() => handleUsePromptIdea("A cozy cabin in the woods with a warm fireplace")}
              >
                Cozy cabin
              </Button>
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-3 mt-4">
          <div className="grid grid-cols-2 gap-3 flex-1">
            <div>
              <Label className="text-sm font-medium mb-1.5 block">
                Image Quality
              </Label>
              <Select 
                value={quality} 
                onValueChange={setQuality}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select quality" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="auto">Auto</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <Label className="text-sm font-medium mb-1.5 block">
                Output Format
              </Label>
              <Select 
                value={outputFormat} 
                onValueChange={setOutputFormat}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select format" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="png">PNG</SelectItem>
                  <SelectItem value="webp">WebP</SelectItem>
                  <SelectItem value="jpeg">JPEG</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          
          <Button 
            type="submit" 
            className="gap-2 h-10"
            disabled={isLoading || !prompt.trim()}
          >
            {isLoading ? (
              <>
                <RotateCwIcon className="h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Wand2Icon className="h-4 w-4" />
                Generate
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
} 