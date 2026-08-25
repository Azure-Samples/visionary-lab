import { useState, useEffect, useRef, useMemo } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { X, Wand2, Loader2, ArrowUp, Images, FolderTree, Plus, Check, RefreshCw, PlusCircle, Eye } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { cn } from "@/utils/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { enhanceImagePrompt, createFolder, fetchFolders } from "@/services/api";
import { toast } from "sonner";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Input } from "@/components/ui/input";
import { useImageSettings } from "@/context/image-settings-context";
import { useFolderContext } from "@/context/folder-context";

interface ImageOverlayProps {
  onGenerate: (settings: {
    prompt: string;
    model: string;
    imageSize: string;
    brandsProtection: string;
    variations: number;
    folder: string;
    background: string;
    outputFormat: string;
    quality: string;
    inputFidelity: string;
    analyze: boolean;
    sourceImages?: File[];
    brandsList?: string[];
  }) => Promise<void>;
  isSubmitting?: boolean;
  folders?: string[];
  selectedFolder?: string;
  onFolderCreated?: (newFolder: string | string[]) => void;
}

const STANDARD_IMAGE_SIZES = [
  ["auto", "Auto"],
  ["1024x1024", "1024 × 1024"],
  ["1536x1024", "1536 × 1024"],
  ["1024x1536", "1024 × 1536"],
] as const;

const GPT_IMAGE_2_SIZES = [
  ...STANDARD_IMAGE_SIZES,
  ["2048x2048", "2048 × 2048"],
  ["3840x2160", "3840 × 2160 (4K)"],
  ["2160x3840", "2160 × 3840 (4K portrait)"],
] as const;

export function ImageOverlay({ 
  onGenerate, 
  isSubmitting = false,
  folders = [],
  selectedFolder = "",
  onFolderCreated
}: ImageOverlayProps) {
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("gpt-image-2");
  const [imageSize, setImageSize] = useState("1024x1024");
  const imageSettings = useImageSettings();
  const [aiAnalysisEnabled, setAiAnalysisEnabled] = useState(true);
  const [variations, setVariations] = useState("1");
  const [isWizardEnhancing, setIsWizardEnhancing] = useState(false);
  const [folder, setFolder] = useState(selectedFolder || "root");
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [isCreatingFolderLoading, setIsCreatingFolderLoading] = useState(false);
  const [isRefreshingFolders, setIsRefreshingFolders] = useState(false);
  const [background, setBackground] = useState("auto");
  const [outputFormat, setOutputFormat] = useState("png");
  const [quality, setQuality] = useState("high");
  const [inputFidelity, setInputFidelity] = useState("low");
  const [sourceImages, setSourceImages] = useState<File[]>([]);
  const isFluxModel = model.toLowerCase().includes("flux");
  const imageSizeOptions: ReadonlyArray<readonly [string, string]> = isFluxModel
    ? STANDARD_IMAGE_SIZES
    : GPT_IMAGE_2_SIZES;
  
  // Reference to the textarea element
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const newFolderInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const { refreshFolders } = useFolderContext();

  // Stable object URLs for source images — revoked on cleanup to prevent memory leaks
  const imageUrls = useMemo(() => {
    const urls = sourceImages.map(img => URL.createObjectURL(img));
    return urls;
  }, [sourceImages]);

  useEffect(() => {
    return () => {
      imageUrls.forEach(url => URL.revokeObjectURL(url));
    };
  }, [imageUrls]);

  // Update folder when selectedFolder prop changes
  useEffect(() => {
    setFolder(selectedFolder || "root");
  }, [selectedFolder]);

  useEffect(() => {
    if (
      isFluxModel &&
      !STANDARD_IMAGE_SIZES.some(([value]) => value === imageSize)
    ) {
      setImageSize("1024x1024");
    }
  }, [imageSize, isFluxModel]);

  // Focus the new folder input when creating folder
  useEffect(() => {
    if (isCreatingFolder && newFolderInputRef.current) {
      newFolderInputRef.current.focus();
    }
  }, [isCreatingFolder]);
  
  // Resize textarea when prompt changes (especially after AI enhancement)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      // Only auto-resize if we haven't hit the max height
      const scrollHeight = textareaRef.current.scrollHeight;
      if (scrollHeight <= 200) {
        textareaRef.current.style.height = `${scrollHeight}px`;
      } else {
        textareaRef.current.style.height = '200px';
      }
    }
  }, [prompt]);

  // Effect to handle format compatibility with transparent background
  useEffect(() => {
    if (background === "transparent" && outputFormat === "jpeg") {
      setOutputFormat("png");
    }
  }, [background, outputFormat]);

  const handleSubmit = () => {
    if (prompt.trim() === "") {
      toast.error("Please enter a prompt");
      return;
    }
    
    const numVariations = parseInt(variations);
    
    if (isNaN(numVariations) || numVariations < 1 || numVariations > 10) {
      toast.error("Please select a valid number of variations (1-10)");
      return;
    }
    
    const generationSettings = {
      prompt,
      model,
      imageSize,
      brandsProtection: imageSettings.settings.brandsProtection,
      variations: numVariations,
      folder,
      background,
      outputFormat,
      quality,
      inputFidelity,
      analyze: aiAnalysisEnabled,
      sourceImages,
      brandsList: imageSettings.settings.brandsList
    };

    void onGenerate(generationSettings);

    if (sourceImages.length === 0) {
      setPrompt("");
      window.requestAnimationFrame(() => textareaRef.current?.focus());
    }
  };

  const handleWizardEnhance = async () => {
    if (!prompt.trim() || isSubmitting || isWizardEnhancing) return;
    
    // Set loading state
    setIsWizardEnhancing(true);
    
    try {
      // Call the API to enhance the prompt
      const enhancedPrompt = await enhanceImagePrompt(prompt.trim());
      
      // Update the prompt with the enhanced version
      setPrompt(enhancedPrompt);
      
      // Show success message
      toast.success("Prompt enhanced", {
        description: "Your prompt has been enhanced with AI"
      });
    } catch (error) {
      console.error("Error enhancing prompt:", error);
      toast.error("Failed to enhance prompt", {
        description: "Please try again or adjust your prompt"
      });
    } finally {
      // Reset loading state
      setIsWizardEnhancing(false);
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    
    try {
      setIsCreatingFolderLoading(true);
      
      // Call the API to create the folder
      const result = await createFolder(newFolderName.trim());
      
      if (result.success) {
        // Show success message
        toast.success("Folder created", {
          description: `Folder "${newFolderName}" has been created successfully`
        });
        
        // Get the new folder path
        const newFolderPath = result.folder_path;
        
        // Reset the form
        setNewFolderName("");
        setIsCreatingFolder(false);
        
        // Select the newly created folder
        setFolder(newFolderPath);
        
        // Notify parent component about the new folder
        if (onFolderCreated) {
          onFolderCreated(newFolderPath);
        }
        
        // Trigger sidebar refresh
        refreshFolders();
      }
    } catch (error) {
      console.error("Error creating folder:", error);
      toast.error("Failed to create folder", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
    } finally {
      setIsCreatingFolderLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleCreateFolder();
    } else if (e.key === 'Escape') {
      setIsCreatingFolder(false);
      setNewFolderName("");
    }
  };

  // Function to refresh the folders list
  const handleRefreshFolders = async () => {
    if (isRefreshingFolders) return;
    
    try {
      setIsRefreshingFolders(true);
      
      const result = await fetchFolders();
      
      if (result.folders && onFolderCreated) {
        // Update the parent component with the full folder list
        onFolderCreated(result.folders);
        
        // Trigger sidebar refresh
        refreshFolders();
        
        toast.success("Folders refreshed", {
          description: `${result.folders.length} folders available`
        });
      }
    } catch (error) {
      console.error("Error refreshing folders:", error);
      toast.error("Failed to refresh folders", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
    } finally {
      setIsRefreshingFolders(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      const validFiles: File[] = [];
      
      for (const file of files) {
        // Validate file type
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
          toast.error("Invalid file type", {
            description: `${file.name}: Only JPEG, PNG, and WebP images are supported`
          });
          continue;
        }
        
        // Validate file size
        if (file.size >= 50 * 1024 * 1024) {
          toast.error("File too large", {
            description: `${file.name}: Images must be less than 50MB`
          });
          continue;
        }
        
        validFiles.push(file);
      }
      
      // GPT-Image-2 supports up to 10 reference images.
      if (sourceImages.length + validFiles.length > 10) {
        toast.warning("Too many images", {
          description: "Maximum 10 images can be selected"
        });
        
        // Take only what we can fit
        const spaceLeft = 10 - sourceImages.length;
        validFiles.splice(spaceLeft);
      }
      
      if (validFiles.length > 0) {
        setSourceImages(prev => [...prev, ...validFiles]);
        
        toast.success("Images selected", {
          description: `Added ${validFiles.length} image${validFiles.length > 1 ? 's' : ''}`
        });
      }
    }
  };
  
  // Handle image removal - now removes a specific image by index
  const handleRemoveImage = (index: number) => {
    setSourceImages(prev => prev.filter((_, i) => i !== index));
  };
  
  // Handle clearing all images
  const handleClearAllImages = () => {
    setSourceImages([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const getSubmitButtonLabel = (): string => {
    if (isSubmitting) {
      return sourceImages.length > 0 ? "Editing..." : "Starting...";
    }
    if (sourceImages.length > 0) {
      return "Edit Images";
    }
    return "Generate";
  };

  return (
    <div className="flex items-end justify-center p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] sm:p-6 sm:pb-[max(1.5rem,env(safe-area-inset-bottom))] pointer-events-none">
      <div className={cn(
        "w-full transition-all duration-300 ease-in-out pointer-events-auto mb-2 sm:mb-6"
      )}
      style={{
        maxWidth: sourceImages.length > 0 ? '58rem' : '56rem'
      }}>
        <div className={cn(
          "rounded-xl p-4 shadow-lg border",
          "backdrop-blur-md bg-white/90 dark:bg-black/70 border-black/10 dark:border-white/10 shadow-lg dark:shadow-none"
        )}>
          <div className="flex flex-col space-y-4">
            {/* Image thumbnails row */}
            {sourceImages.length > 0 && (
              <div className="flex flex-wrap gap-2 items-center">
                {sourceImages.map((img, index) => (
                  <div key={index} className="relative">
                    <div className="relative h-12 w-12">
                      <Image 
                        src={imageUrls[index]} 
                        alt={`${img.name}, source image ${index + 1}`}
                        fill
                        className={cn(
                          "rounded-md border object-cover transition-all duration-200",
                          index === 0 && sourceImages.length > 1 
                            ? "border-sky-300 ring-2 ring-sky-300/50 shadow-lg shadow-sky-300/25 motion-safe:animate-pulse" 
                            : "border-gray-500/30"
                        )}
                        sizes="48px"
                        unoptimized
                      />
                    </div>
                    {/* Primary image indicator */}
                    {index === 0 && sourceImages.length > 1 && (
                      <div className="absolute -top-1 -right-1 bg-sky-400 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center font-bold">
                        1
                      </div>
                    )}
                    <Button 
                      onClick={() => handleRemoveImage(index)}
                      className={cn(
                        "absolute -top-2 -right-2 rounded-full p-0.5 hover:bg-black",
                        "bg-white/90 text-gray-700 dark:bg-black/70 dark:text-white"
                      )}
                      disabled={isSubmitting}
                      aria-label="Remove image"
                      title="Remove image"
                      variant="ghost"
                      size="icon"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
                {sourceImages.length > 1 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearAllImages}
                    className={cn(
                      "text-xs",
                      "text-gray-500 dark:text-white/70",
                      "hover:bg-gray-200/50 dark:hover:bg-white/10"
                    )}
                    disabled={isSubmitting}
                  >
                    Clear all
                  </Button>
                )}
              </div>
            )}
            
            {/* Input row with buttons */}
            <div className="flex items-start gap-1.5 sm:gap-3">
             <TooltipProvider>
              <Tooltip delayDuration={300}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (fileInputRef.current) {
                          fileInputRef.current.click();
                        }
                      }}
                      aria-label="Upload images"
                      className={cn(
                        "mt-1",
                        "text-gray-500 dark:text-white/70",
                        "hover:bg-gray-200/50 dark:hover:bg-white/10"
                      )}
                      disabled={isSubmitting}
                    >
                      <PlusCircle className="h-5 w-5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="left" className="font-medium">
                    <p>Upload images to edit (max 10)</p>
                  </TooltipContent>
                </Tooltip>
              
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                disabled={isSubmitting}
                aria-label="Upload image files"
                multiple
              />
              
              <div className="relative min-w-0 flex-1">
                <Textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder={sourceImages.length > 0 ? "Describe how to edit these images..." : "Describe your image..."}
                  aria-label={sourceImages.length > 0 ? "Image editing instructions" : "Image prompt"}
                  className={cn(
                    "border border-gray-500/30 min-h-[40px] max-h-[200px] resize-none px-3 py-2 overflow-y-auto",
                    "bg-white/50 border-gray-200 text-gray-900 focus:ring-gray-200",
                    "dark:bg-black/30 dark:border-0 dark:text-white dark:focus:ring-white/20"
                  )}
                  disabled={isSubmitting}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && prompt.trim() && !isSubmitting) {
                      e.preventDefault();
                      handleSubmit();
                    }
                  }}
                  onInput={(e) => {
                    // Auto-resize textarea
                    const target = e.target as HTMLTextAreaElement;
                    // Only auto-resize if we haven't hit the max height
                    if (target.scrollHeight <= 200) {
                      target.style.height = 'auto';
                      target.style.height = `${target.scrollHeight}px`;
                    }
                  }}
                  rows={1}
                  ref={textareaRef}
                />
              </div>
              
              <div className="mt-1 flex shrink-0 items-start gap-1 sm:gap-2">
                <Tooltip delayDuration={300}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={handleWizardEnhance}
                        aria-label="Enhance prompt"
                        className={cn(
                          "border-0 min-w-9 h-9",
                          "bg-gray-100 hover:bg-gray-200 text-gray-900",
                          "dark:bg-white/10 dark:hover:bg-white/20 dark:text-white"
                        )}
                        disabled={isSubmitting || isWizardEnhancing || !prompt.trim()}
                      >
                        {isWizardEnhancing ? (
                          <Loader2 className="h-4 w-4 motion-safe:animate-spin" />
                        ) : (
                          <Wand2 className="h-4 w-4" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="left" className="font-medium">
                      <p>Enhance your prompt with AI</p>
                    </TooltipContent>
                  </Tooltip>
                
                <Button
                  variant="outline"
                  onClick={handleSubmit}
                  aria-label={getSubmitButtonLabel()}
                  className={cn(
                    "border-0",
                    "bg-gray-100 hover:bg-gray-200 text-gray-900",
                    "dark:bg-white/10 dark:hover:bg-white/20 dark:text-white"
                  )}
                  disabled={isSubmitting || !prompt.trim()}
                >
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 sm:mr-2 motion-safe:animate-spin" />
                  ) : (
                    <ArrowUp className="h-4 w-4 sm:mr-2" />
                  )}
                  <span className="hidden sm:inline">{getSubmitButtonLabel()}</span>
                </Button>
              </div>
             </TooltipProvider>
            </div>

              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <TooltipProvider>
                  <div className="flex flex-wrap items-center gap-1.5 w-full">
                    {/* Model */}
                    <Select value={model} onValueChange={setModel} disabled={isSubmitting}>
                      <SelectTrigger aria-label="Image model" className="h-7 w-auto gap-1 px-2.5 text-xs rounded-md border-0 bg-muted/50 hover:bg-muted">
                        <span>{
                          { "gpt-image-2": "GPT-Image-2", "flux-kontext-pro": "FLUX Kontext Pro" }[model] ?? model
                        }</span>
                      </SelectTrigger>
                      <SelectContent align="start">
                        <SelectItem value="gpt-image-2" className="py-2">
                          <div className="flex flex-col">
                            <span>GPT-Image-2</span>
                            <span className="text-xs text-muted-foreground">High fidelity, flexible sizes, 4K</span>
                          </div>
                        </SelectItem>
                        <SelectItem value="flux-kontext-pro" className="py-2">
                          <div className="flex flex-col">
                            <span>FLUX Kontext Pro</span>
                            <span className="text-xs text-muted-foreground">FLUX.1-Kontext-pro</span>
                          </div>
                        </SelectItem>
                      </SelectContent>
                    </Select>

                    <span className="text-muted-foreground/40" aria-hidden="true">·</span>

                    {/* Size */}
                    <Select value={imageSize} onValueChange={setImageSize} disabled={isSubmitting}>
                      <SelectTrigger aria-label="Image size" className="h-7 w-auto gap-1 px-2.5 text-xs rounded-md border-0 bg-muted/50 hover:bg-muted">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent align="start">
                        {imageSizeOptions.map(([value, label]) => (
                          <SelectItem key={value} value={value}>{label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {/* Background — gpt-image models only */}
                    {!isFluxModel && (
                    <Select value={background} onValueChange={setBackground} disabled={isSubmitting}>
                      <SelectTrigger aria-label="Image background" className="h-7 w-auto gap-1 px-2.5 text-xs rounded-md border-0 bg-muted/50 hover:bg-muted">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent align="start">
                        <SelectItem value="auto">Auto</SelectItem>
                        <SelectItem value="transparent">Transparent</SelectItem>
                        <SelectItem value="opaque">Opaque</SelectItem>
                      </SelectContent>
                    </Select>
                    )}

                    {/* Format — gpt-image models only */}
                    {!isFluxModel && (
                    <Select value={outputFormat} onValueChange={setOutputFormat} disabled={isSubmitting}>
                      <SelectTrigger aria-label="Output format" className="h-7 w-auto gap-1 px-2.5 text-xs rounded-md border-0 bg-muted/50 hover:bg-muted">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent align="start">
                        <SelectItem value="png">PNG</SelectItem>
                        <SelectItem value="jpeg" disabled={background === "transparent"}>JPEG</SelectItem>
                      </SelectContent>
                    </Select>
                    )}

                    {/* Quality — gpt-image models only */}
                    {!isFluxModel && (
                    <Select value={quality} onValueChange={setQuality} disabled={isSubmitting}>
                      <SelectTrigger aria-label="Image quality" className="h-7 w-auto gap-1 px-2.5 text-xs rounded-md border-0 bg-muted/50 hover:bg-muted">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent align="start">
                        <SelectItem value="low">Low</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                      </SelectContent>
                    </Select>
                    )}

                    {/* Fidelity — only when editing images */}
                    {sourceImages.length > 0 && (
                      <Select value={inputFidelity} onValueChange={setInputFidelity} disabled={isSubmitting}>
                        <SelectTrigger aria-label="Input fidelity" className="h-7 w-auto gap-1 px-2.5 text-xs rounded-md border-0 bg-muted/50 hover:bg-muted motion-safe:animate-in motion-safe:fade-in-0 duration-200">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent align="start">
                          <SelectItem value="low">Low fidelity</SelectItem>
                          <SelectItem value="high">High fidelity</SelectItem>
                        </SelectContent>
                      </Select>
                    )}

                    <span className="text-muted-foreground/40" aria-hidden="true">·</span>

                    {/* Variations */}
                    <Select value={variations} onValueChange={setVariations} disabled={isSubmitting}>
                      <SelectTrigger aria-label="Number of images" className="h-7 w-auto gap-1 px-2.5 text-xs rounded-md border-0 bg-muted/50 hover:bg-muted">
                        <Images className="h-3 w-3 opacity-60" />
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent align="start">
                        {Array.from({ length: 10 }, (_, i) => (
                          <SelectItem key={i + 1} value={String(i + 1)}>{i + 1}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {/* Folder & Analysis */}
                         {/* Folder Select Dropdown */}
                        <Tooltip delayDuration={300}>
                          <TooltipTrigger asChild>
                            <div className="relative motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-left-2 duration-300">
                          <Select
                            value={folder}
                            onValueChange={setFolder}
                            disabled={isSubmitting}
                            onOpenChange={(open) => {
                              if (!open) {
                                setIsCreatingFolder(false);
                                setNewFolderName("");
                              }
                            }}
                          >
                            <SelectTrigger aria-label="Destination folder" className="w-[130px] h-8">
                              <div className="flex items-center">
                                <FolderTree className="h-4 w-4 mr-2 text-primary" />
                                <SelectValue placeholder="Root" />
                              </div>
                            </SelectTrigger>
                            <SelectContent>
                              {/* Create Folder UI */}
                              {isCreatingFolder ? (
                                <div className="flex items-center p-1 mb-1 border-b border-muted">
                                  <Input
                                    ref={newFolderInputRef}
                                    value={newFolderName}
                                    onChange={(e) => setNewFolderName(e.target.value)}
                                    placeholder="New folder name..."
                                    aria-label="New folder name"
                                    className="h-7 text-xs border-0 focus-visible:ring-0 bg-muted/50"
                                    onKeyDown={handleKeyDown}
                                    disabled={isCreatingFolderLoading}
                                  />
                                  <Button
                                    size="icon"
                                    variant="ghost"
                                    className="h-7 w-7"
                                    onClick={handleCreateFolder}
                                    disabled={!newFolderName.trim() || isCreatingFolderLoading}
                                    aria-label="Create folder"
                                  >
                                    {isCreatingFolderLoading ? (
                                      <Loader2 className="h-3 w-3 motion-safe:animate-spin" />
                                    ) : (
                                      <Check className="h-3 w-3" />
                                    )}
                                  </Button>
                                </div>
                              ) : (
                                <div className="flex items-center justify-between p-1 mb-1 border-b border-muted">
                                  <span className="text-xs text-muted-foreground ml-2">Folders</span>
                                  <div className="flex items-center gap-1">
                                    <Button
                                      size="icon"
                                      variant="ghost"
                                      className="h-6 w-6"
                                      onClick={handleRefreshFolders}
                                      disabled={isRefreshingFolders}
                                      aria-label="Refresh folders"
                                    >
                                      <RefreshCw className={`h-3 w-3 ${isRefreshingFolders ? 'motion-safe:animate-spin' : ''}`} />
                                    </Button>
                                    <Button
                                      size="icon"
                                      variant="ghost"
                                      className="h-6 w-6"
                                      onClick={() => {
                                        setIsCreatingFolder(true);
                                        // Focus the input after a small delay to allow rendering
                                        setTimeout(() => {
                                          if (newFolderInputRef.current) {
                                            newFolderInputRef.current.focus();
                                          }
                                        }, 10);
                                      }}
                                      aria-label="Create a new folder"
                                    >
                                      <Plus className="h-3 w-3" />
                                    </Button>
                                  </div>
                                </div>
                              )}
                              
                              <SelectItem value="root">Root</SelectItem>
                              {folders.map((folderPath) => (
                                <SelectItem key={folderPath} value={folderPath}>
                                  {folderPath}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        <p>Storage location for generated image files</p>
                      </TooltipContent>
                    </Tooltip>

                        {/* AI Analysis Toggle Button */}
                        <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <ToggleGroup 
                          type="single" 
                          size="lg"
                          value={aiAnalysisEnabled ? "analyze" : ""}
                          onValueChange={(value) => {
                            setAiAnalysisEnabled(value === "analyze");
                          }}
                          disabled={isSubmitting}
                        >
                          <ToggleGroupItem 
                            value="analyze" 
                            aria-label="Analyze generated images"
                            className={cn(
                              "rounded-md w-10 h-8 p-2 flex items-center justify-center transition-colors duration-200",
                              aiAnalysisEnabled
                                ? "bg-gray-300/50 border border-gray-300/50 text-gray-900 dark:bg-white/15 dark:border-white/30 dark:text-white"
                                : "bg-white/50 border border-gray-200/50 text-gray-500 dark:bg-black/30 dark:border-white/10 dark:text-white/60"
                            )}
                          >
                            <Eye className="h-4 w-4" />
                          </ToggleGroupItem>
                        </ToggleGroup>
                      </TooltipTrigger>
                      <TooltipContent side="left" className="font-medium">
                        <p>Analyze images for automatic tagging and summary</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </TooltipProvider>
              </div>
          </div>
        </div>
      </div>
    </div>
  );
} 
