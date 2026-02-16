"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ImageUploader } from "@/components/ImageUploader";
import { ChatInput } from "@/components/simple-ai/chat-input";
import { AnalysisResults } from "@/components/AnalysisResults";
import { Button } from "@/components/ui/button";
import { analyzeImageCustom, type ImageAnalysisResponse } from "@/services/api";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import dynamic from "next/dynamic";
const PageTransition = dynamic(() => import("@/components/ui/page-transition").then(m => ({ default: m.PageTransition })), { ssr: false });
import { useImageSettings } from "@/context/image-settings-context";

export default function AnalyzePage() {
  const { settings } = useImageSettings();
  const [uploadedImage, setUploadedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [customPrompt, setCustomPrompt] = useState("");
  const [analysisResults, setAnalysisResults] = useState<ImageAnalysisResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Initialize with default prompt from settings
  useEffect(() => {
    if (settings.customAnalysisPrompt && !customPrompt) {
      setCustomPrompt(settings.customAnalysisPrompt);
    }
  }, [settings.customAnalysisPrompt, customPrompt]);

  const handleImageUpload = (file: File) => {
    setUploadedImage(file);
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(file);
    
    // Clear previous results when new image is uploaded
    setAnalysisResults(null);
  };

  const handleAnalyze = async () => {
    if (!uploadedImage || !customPrompt.trim()) {
      toast.error("Please upload an image and enter a custom prompt");
      return;
    }

    setIsAnalyzing(true);
    try {
      // Convert to base64 for API call
      const reader = new FileReader();
      reader.onload = async (e) => {
        const base64 = e.target?.result as string;
        const cleanBase64 = base64.split(',')[1]; // Remove data:image prefix
        
        const results = await analyzeImageCustom(undefined, cleanBase64, customPrompt);
        setAnalysisResults(results);
        toast.success("Analysis completed!");
      };
      reader.readAsDataURL(uploadedImage);
    } catch (error) {
      console.error('Analysis failed:', error);
      toast.error("Analysis failed", {
        description: error instanceof Error ? error.message : "Unknown error"
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handlePromptTemplate = (template: string) => {
    setCustomPrompt(template);
  };

  const promptTemplates = [
    "Analyze this image for marketing effectiveness and target audience appeal",
    "Describe the technical composition, lighting, and photography techniques used", 
    "Identify accessibility issues and suggest improvements",
    "Analyze color psychology and emotional impact",
    "Evaluate this image for social media engagement potential",
    "Assess the brand consistency and visual identity elements"
  ];

  return (
    <PageTransition>
      <div className="container mx-auto p-6 space-y-6">
        <PageHeader title="Custom Image Analysis" />
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Input Panel */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Upload Image</CardTitle>
              </CardHeader>
              <CardContent>
                <ImageUploader 
                  onImageSelected={handleImageUpload}
                  maxSize={10 * 1024 * 1024} // 10MB limit
                />
                {imagePreview && (
                  <div className="mt-4">
                    <div className="relative mx-auto h-64 w-full max-w-md">
                      <Image 
                        src={imagePreview} 
                        alt="Preview" 
                        fill
                        className="object-contain rounded-lg border"
                        sizes="(max-width: 768px) 100vw, 33vw"
                        unoptimized
                      />
                    </div>
                    <p className="text-xs text-muted-foreground text-center mt-2">
                      {uploadedImage?.name} ({Math.round((uploadedImage?.size || 0) / 1024)}KB)
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Custom Analysis Prompt</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <ChatInput
                  value={customPrompt}
                  onChange={setCustomPrompt}
                  onSubmit={handleAnalyze}
                  placeholder="Enter your custom analysis prompt... (e.g., 'Analyze this image for marketing effectiveness, color psychology, and target audience appeal')"
                  disabled={isAnalyzing}
                  submitLabel={isAnalyzing ? "Analyzing..." : "Analyze Image"}
                  maxRows={4}
                />
                
                <div className="flex justify-between items-center">
                  <Button 
                    onClick={handleAnalyze} 
                    disabled={!uploadedImage || !customPrompt.trim() || isAnalyzing}
                    className="w-full"
                  >
                    {isAnalyzing ? "Analyzing..." : "Analyze Image"}
                  </Button>
                </div>
                
                {/* Quick Templates */}
                <div className="space-y-3">
                  <p className="text-sm font-medium">Quick templates:</p>
                  <div className="flex flex-wrap gap-2">
                    {promptTemplates.map((template, idx) => (
                      <Badge
                        key={idx}
                        variant="outline"
                        className="cursor-pointer hover:bg-muted transition-colors text-xs"
                        onClick={() => handlePromptTemplate(template)}
                      >
                        {template.slice(0, 40)}...
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Results Panel */}
          <div>
            <AnalysisResults 
              results={analysisResults}
              isLoading={isAnalyzing}
              customPrompt={customPrompt}
            />
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
