"use client";

import { useState, useEffect } from "react";
import { ImageOverlay } from "./ImageOverlay";
import { toast } from "sonner";
import { cn } from "@/utils/utils";
import { 
  generateImages, 
  saveGeneratedImages, 
  analyzeImageFromBase64, 
  MediaType, 
  fetchFolders, 
  editImage,
  protectImagePrompt 
} from "@/services/api";

interface ImageCreationContainerProps {
  className?: string;
  onImagesSaved?: (count?: number) => void;
}

interface ImageGenerationSettings {
  prompt: string;
  imageSize: string;
  saveImages: boolean;
  mode: string;
  brandsProtection: string;
  brandProtectionModel: string;
  variations: number;
  folder: string;
  background: string;
  outputFormat: string;
  quality: string;
  inputFidelity: string;
  sourceImages?: File[];
  brandsList?: string[];
}

interface ImageData {
  b64_json?: string;
  url?: string;
}

interface AnalysisResult {
  description: string;
  products: string;
  tags: string[];
  feedback: string;
}

interface ImageAnalysis {
  index: number;
  analysis?: AnalysisResult;
  error?: string;
}

interface BrandProtection {
  originalPrompt: string;
  protectedPrompt: string;
  mode: string;
  brands: string[];
}

interface GenerationResponse {
  imgen_model_response?: {
    data: ImageData[];
    [key: string]: unknown;
  };
  brandProtection?: BrandProtection;
  metadata?: Record<string, string>;
  analysisResults?: ImageAnalysis[];
  [key: string]: unknown;
}

interface SavedImage {
  url: string;
  blob_name: string;
  metadata: Record<string, string>;
}

// Used in type definitions
// eslint-disable-next-line @typescript-eslint/no-unused-vars
interface SaveResponse {
  total_saved: number;
  saved_images: SavedImage[];
}

export function ImageCreationContainer({ className = "", onImagesSaved }: ImageCreationContainerProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [originalPrompt, setOriginalPrompt] = useState<string | null>(null);
  // This state is updated but not directly used in JSX - it's used in handleSaveImages
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [generationResponseData, setGenerationResponseData] = useState<GenerationResponse | null>(null);
  const [folders, setFolders] = useState<string[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>("root");
  const [settings, setSettings] = useState<ImageGenerationSettings>({
    prompt: "",
    imageSize: "1024x1024",
    saveImages: true,
    mode: "prod",
    brandsProtection: "off",
    brandProtectionModel: "GPT-4o",
    variations: 1,
    folder: "root",
    background: "auto",
    outputFormat: "png",
    quality: "auto",
    sourceImages: [] as File[],
    brandsList: [] as string[],
  });

  // Fetch available folders when component mounts
  useEffect(() => {
    const loadFolders = async () => {
      try {
        const result = await fetchFolders(MediaType.IMAGE);
        setFolders(result.folders);
      } catch (error) {
        console.error("Error loading folders:", error);
      }
    };
    
    loadFolders();
  }, []);

  const handleGenerate = async (newSettings: ImageGenerationSettings) => {
    try {
      setIsGenerating(true);
      setSettings({ 
        ...newSettings, 
        sourceImages: newSettings.sourceImages || [],
        brandsList: newSettings.brandsList || []
      });
      setSelectedFolder(newSettings.folder);
      
      // Store the original prompt
      const originalPrompt = newSettings.prompt;
      
      // Apply brand protection if enabled
      let generationPrompt = originalPrompt;
      let brandProtectionApplied = false;
      if (newSettings.brandsProtection !== "off" && newSettings.brandsList && newSettings.brandsList.length > 0) {
        try {
          // Call the brand protection API
          generationPrompt = await protectImagePrompt(
            originalPrompt,
            newSettings.brandsList,
            newSettings.brandsProtection
          );
          
          // Log the difference if in debug mode
          if (generationPrompt !== originalPrompt) {
            
            brandProtectionApplied = true;
          }
        } catch (error) {
          console.error('Error applying brand protection:', error);
          toast.error("Brand protection failed", {
            description: "Using original prompt instead"
          });
          // Fallback to original prompt on error
          generationPrompt = originalPrompt;
        }
      }
      
      let successfulAnalysis: ImageAnalysis[] | undefined = undefined; // Declare outside the if block
      let response;
      
      // If source images are provided, use the edit endpoint
      if (newSettings.sourceImages && newSettings.sourceImages.length > 0) {
        // Show single consolidated toast for image editing
        const editingToast = toast.loading("Editing images...", {
          description: `Processing ${newSettings.sourceImages.length} image${newSettings.sourceImages.length > 1 ? 's' : ''} with your prompt${brandProtectionApplied ? ' (brand protection applied)' : ''}`,
        });
        
        // Call the image edit API with the protected prompt
        response = await editImage(
          newSettings.sourceImages,
          generationPrompt, // Use protected prompt for generation
          newSettings.variations, // Number of variations from dropdown
          newSettings.imageSize, // Use selected size
          newSettings.quality, // Quality parameter
          newSettings.inputFidelity // Input fidelity parameter
        );
        
        // Update the loading toast to success
        toast.success("Image editing completed", {
          id: editingToast,
          description: `Successfully edited ${newSettings.variations} image${newSettings.variations > 1 ? 's' : ''}`
        });
      } else {
        // Show single consolidated toast for image generation
        const generatingToast = toast.loading("Generating images...", {
          description: `Creating ${newSettings.variations} image${newSettings.variations > 1 ? 's' : ''} with your prompt${brandProtectionApplied ? ' (brand protection applied)' : ''}`,
        });
        
        // Call the image generation API with the protected prompt
        response = await generateImages(
          generationPrompt, // Use protected prompt for generation
          newSettings.variations, // Number of variations from dropdown
          newSettings.imageSize, // Use selected size
          "b64_json", // Fixed response format for now
          newSettings.background, // Background option
          newSettings.outputFormat, // Output format
          newSettings.quality // Quality parameter
        );
        
        // Update the loading toast to success
        toast.success("Image generation completed", {
          id: generatingToast,
          description: `Successfully generated ${newSettings.variations} image${newSettings.variations > 1 ? 's' : ''}`
        });
      }
      
      // Store the brand protection info in the response for later use when saving
      response.brandProtection = {
        originalPrompt,
        protectedPrompt: generationPrompt,
        mode: newSettings.brandsProtection,
        brands: newSettings.brandsList
      };
      
      setGenerationResponseData(response);
      
      // If AI analysis is enabled, we can analyze before saving
      if (newSettings.saveImages && newSettings.brandProtectionModel === "GPT-4o") {
        // Check if we have base64 image data available (from generation)
        const hasBase64Images = response?.imgen_model_response?.data?.some(
          (item: ImageData) => item.b64_json
        );
        
        if (hasBase64Images) {
          // Process each image and collect analysis results (silently)
          const analysisPromises = response.imgen_model_response.data.map(
            async (imageData: ImageData, idx: number) => {
              if (imageData.b64_json) {
                try {
                  const result = await analyzeImageFromBase64(imageData.b64_json);
                  return {
                    index: idx,
                    analysis: result
                  };
                } catch (error) {
                  console.error(`Failed to analyze image ${idx+1}:`, error);
                  return {
                    index: idx,
                    error: error instanceof Error ? error.message : String(error)
                  };
                }
              }
              return null;
            }
          );
          
          const analysisResults = await Promise.all(analysisPromises);
          successfulAnalysis = analysisResults.filter(r => r && r.analysis); // Assign here
          
          // Store analysis results to use when saving (no toast needed)
          if (successfulAnalysis.length > 0) {
            setGenerationResponseData((prev: GenerationResponse | null) => ({
              ...(prev || {}),
              analysisResults: successfulAnalysis
            }));
          }
        }
      }
      
      // If saveImages is true, proceed to upload
      if (newSettings.saveImages) {
        await handleSaveImages(
          response, 
          response.brandProtection?.originalPrompt || originalPrompt, // Use original prompt (not protected) for saving metadata
          true, // Enable analysis for testing
          newSettings.folder === "root" ? "" : newSettings.folder,
          newSettings.outputFormat,
          newSettings.background,
          newSettings.imageSize,
          successfulAnalysis // Pass pre-analysis results directly
        );
      }
      
    } catch (error) {
      console.error('Error in image operation:', error);
      const hasSourceImages = newSettings.sourceImages && newSettings.sourceImages.length > 0;
      toast.error(hasSourceImages ? "Image editing failed" : "Image generation failed", {
        description: error instanceof Error ? error.message : "Unknown error occurred"
      });
    } finally {
      setIsGenerating(false);
    }
  };
  
  const handleSaveImages = async (
    generationResponse: GenerationResponse, 
    prompt: string, 
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _shouldAnalyze: boolean = false, 
    folder: string = "",
    outputFormat: string = "png",
    background: string = "auto",
    imageSize: string,
    preAnalysisResults?: ImageAnalysis[] 
  ) => {
    try {
      setIsUploading(true);
      
      // Show consolidated saving toast
      const savingToast = toast.loading("Saving images...", {
        description: `Uploading to ${folder || 'root folder'}${preAnalysisResults && preAnalysisResults.length > 0 ? ' with AI analysis' : ''}...`
      });
      
      // Add brand protection metadata if available
      const hasBrandProtection = generationResponse?.brandProtection && 
                                generationResponse.brandProtection.mode !== "off" &&
                                generationResponse.brandProtection.brands && 
                                generationResponse.brandProtection.brands.length > 0;
      
      // Create a copy of generationResponse with additional metadata
      const enhancedResponse = { ...generationResponse };
      
      // Add brand protection metadata to the response before saving
      if (hasBrandProtection) {
        try {
          enhancedResponse.metadata = {
            ...(enhancedResponse.metadata || {}),
            brand_protection_mode: generationResponse.brandProtection!.mode,
            protected_brands: generationResponse.brandProtection!.brands.join(', '),
            protected_prompt: generationResponse.brandProtection!.protectedPrompt
          };
        } catch (error) {
          console.error("Error adding brand protection metadata:", error);
        }
      }
      
      // Determine if we should analyze images (for now, let's make it configurable)
      const shouldAnalyze = _shouldAnalyze; // Use the parameter passed to the function
      
      // Call the save images API with analysis if needed
      const saveResponse = await saveGeneratedImages(
        enhancedResponse, // Use enhanced response with metadata
        generationResponse?.brandProtection?.originalPrompt || prompt, // Use original prompt (not protected) for saving metadata
        true, // Save all generated images
        folder, // Folder path
        outputFormat, // Output format
        "gpt-image-1", // Model - This is always gpt-image-1 in our current implementation
        background, // Background setting
        imageSize, // Pass imageSize here
        shouldAnalyze // Analyze images in the backend if we have pre-analysis results
      );
      
      // Update the loading toast to success with analysis info
      const analysisInfo = saveResponse.analyzed && saveResponse.analysis_results 
        ? ` and analyzed ${saveResponse.analysis_results.filter(r => r.success).length} images`
        : '';
      
      toast.success(`${saveResponse.total_saved} images saved${analysisInfo}`, {
        id: savingToast,
        description: folder 
          ? `Successfully saved to folder: ${folder}` 
          : "Successfully saved to root folder"
      });
      
      // Analysis is now handled in the backend - no more roundtrips needed!
      // The analysis results are already stored in Cosmos DB
      
      // Call the callback to refresh the gallery
      if (onImagesSaved) {
        onImagesSaved(saveResponse.total_saved);
      }
      
    } catch (error) {
      console.error('Error saving images:', error);
      toast.error("Failed to save images", {
        description: error instanceof Error ? error.message : "Unknown error occurred"
      });
    } finally {
      setIsUploading(false);
      setIsAnalyzing(false);
    }
  };

  const handlePromptChange = (newPrompt: string, isEnhanced: boolean) => {
    // Store the original prompt if this is an enhanced version
    if (isEnhanced && !originalPrompt) {
      setOriginalPrompt(settings.prompt);
    }
    
    setSettings(prev => ({
      ...prev,
      prompt: newPrompt
    }));
  };

  // Handle folder creation or updates from the ImageOverlay component
  const handleFolderCreated = (newFolder: string | string[]) => {
    // Update folders list with deduplication
    setFolders(prevFolders => {
      // Handle both single folder and array of folders
      const foldersToAdd = Array.isArray(newFolder) ? newFolder : [newFolder];
      
      // Create a new set with all folders (automatically deduplicates)
      const uniqueFolders = new Set([...prevFolders, ...foldersToAdd]);
      
      // Convert back to array and sort alphabetically
      return Array.from(uniqueFolders).sort((a, b) => a.localeCompare(b));
    });
    
    // Update selected folder (only if a single folder was added)
    if (!Array.isArray(newFolder)) {
      setSelectedFolder(newFolder);
    }
  };

  return (
    <div className={cn("relative w-full h-full", className)}>
      {/* The ImageOverlay component will be positioned absolutely */}
      <ImageOverlay 
        onGenerate={handleGenerate} 
        isGenerating={isGenerating || isUploading || isAnalyzing}
        onPromptChange={handlePromptChange}
        folders={folders}
        selectedFolder={selectedFolder}
        onFolderCreated={handleFolderCreated}
      />
    </div>
  );
} 