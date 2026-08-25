'use client';

import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { InfoIcon, ImageIcon } from 'lucide-react';
import ImageUploader from './ImageUploader';
import ImageCanvas from './ImageCanvas';
import ResultDisplay from './ResultDisplay';
import { Skeleton } from '@/components/ui/skeleton';
import { editImage, saveGeneratedImage, getImageFromResponse, getTokenUsage, ImageGenerationResponse } from '@/services/imageService';
import { toast } from "sonner";

type EditorState = 'draw' | 'result';

interface UploadedImage {
  file: File;
  url: string;
  width: number;
  height: number;
}

export default function EditorContainer() {
  const [editorState, setEditorState] = useState<EditorState>('draw');
  const [uploadedImage, setUploadedImage] = useState<UploadedImage | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [resultData, setResultData] = useState<{
    imageUrl: string;
    model: string;
    prompt: string;
    outputFormat: string;
    size: string;
    background: string;
    tokenUsage?: {
      total: number;
      input: number;
      output: number;
    } | null;
    rawResponse?: ImageGenerationResponse;
  } | null>(null);
  
  // Handle the image upload
  const handleImageUpload = (imageFile: File) => {
    setIsLoading(true);
    
    // Create an object URL for the uploaded file
    const imageUrl = URL.createObjectURL(imageFile);
    
    // Get image dimensions
    const img = new Image();
    img.onload = () => {
      setUploadedImage({
        file: imageFile,
        url: imageUrl,
        width: img.width,
        height: img.height
      });
      setIsLoading(false);
    };
    img.onerror = () => {
      setIsLoading(false);
      toast.error("Error loading image", {
        description: "There was a problem loading your image. Please try again with a different file."
      });
    };
    img.src = imageUrl;
  };
  
  // Reset the editor
  const handleReset = () => {
    if (uploadedImage) {
      URL.revokeObjectURL(uploadedImage.url);
    }
    if (resultData && resultData.imageUrl.startsWith('blob:')) {
      URL.revokeObjectURL(resultData.imageUrl);
    }
    setUploadedImage(null);
    setResultData(null);
    setEditorState('draw');
  };
  
  // Handle mask completion
  const handleMaskComplete = (maskCanvas: HTMLCanvasElement, formData: FormData) => {
    handleSubmit(formData);
  };
  
  // Handle form submission
  const handleSubmit = async (formData: FormData) => {
    setIsLoading(true);
    
    try {
      // Call the API to edit the image
      const response = await editImage(formData);
      
      // Get the image URL and token usage
      const outputFormat = String(formData.get('output_format') ?? 'png');
      const size = String(formData.get('size') ?? 'auto');
      const background = String(formData.get('background') ?? 'auto');
      const imageUrl = getImageFromResponse(response, outputFormat);
      const tokenUsage = getTokenUsage(response);
      const prompt = formData.get('prompt') as string;
      const model = formData.get('model') as string;
      
      // Set the result data
      setResultData({
        imageUrl,
        model,
        prompt,
        outputFormat,
        size,
        background,
        tokenUsage: tokenUsage ?? null,
        rawResponse: response
      });
      
      // Update the editor state
      setEditorState('result');
    } catch (error) {
      console.error('Error editing image:', error);
      toast.error("Error editing image", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
    } finally {
      setIsLoading(false);
    }
  };
  
  // Handle saving image to gallery
  const handleSaveImage = async (folder: string = "") => {
    if (!resultData || !resultData.rawResponse) {
      toast.error("Error saving image", {
        description: "No image data available to save"
      });
      return;
    }
    
    try {
      // Save the image to the gallery
      await saveGeneratedImage(
        resultData.rawResponse,
        {
          prompt: resultData.prompt,
          model: resultData.model,
          output_format: resultData.outputFormat,
          size: resultData.size,
          background: resultData.background,
          save_all: false, // Only save the first image
          folder_path: folder // Use folder_path instead of folder
        }
      );
      
      // Show success toast
      toast.success("Image saved", {
        description: `Successfully saved to gallery${folder ? ` in folder: ${folder}` : ''}`
      });
    } catch (error: unknown) {
      console.error('Error saving image:', error);
      toast.error("Error saving image", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
    }
  };

  return (
    <Card className="w-full border-0 shadow-none">
      <CardContent className="p-6">
        <Tabs 
          value={editorState} 
          onValueChange={(value) => {
            if (
              (value === 'draw') ||
              (value === 'result' && resultData)
            ) {
              setEditorState(value as EditorState);
            }
          }}
          className="w-full"
        >
          {isLoading && (
            <div className="w-full py-8">
              <div className="flex flex-col items-center justify-center space-y-4">
                <Skeleton className="h-[300px] w-full max-w-[500px] rounded-md" />
                <div className="space-y-2 w-full max-w-[500px]">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              </div>
            </div>
          )}
          
          {!isLoading && (
            <>
              <TabsContent value="draw" className="mt-0">
                {uploadedImage ? (
                  <ImageCanvas
                    image={uploadedImage}
                    onProceed={handleMaskComplete}
                  />
                ) : (
                  <div className="space-y-4">
                    <Alert>
                      <InfoIcon className="h-4 w-4" />
                      <AlertDescription>
                        Upload an image to get started. Supported formats: PNG, JPEG, WebP. Maximum file size: 50MB.
                      </AlertDescription>
                    </Alert>
                    
                    <ImageUploader onImageUpload={handleImageUpload} />
                  </div>
                )}
              </TabsContent>
              
              <TabsContent value="result" className="mt-0">
                {resultData ? (
                  <ResultDisplay
                    originalImage={uploadedImage!}
                    resultData={resultData}
                    onReset={handleReset}
                    onSave={handleSaveImage}
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 space-y-6 text-center">
                    <ImageIcon className="h-12 w-12 text-primary opacity-80" />
                    <div>
                      <h3 className="text-xl font-medium mb-2">No Results Yet</h3>
                      <p className="text-muted-foreground">
                        Generate an image to see the results here.
                      </p>
                    </div>
                  </div>
                )}
              </TabsContent>
            </>
          )}
        </Tabs>
      </CardContent>
    </Card>
  );
}
