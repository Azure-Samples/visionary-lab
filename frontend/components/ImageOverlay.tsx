import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { X, Settings, Wand2, Loader2, ArrowUp, Images, FolderTree, Plus, Check, RefreshCw, Layers, FileType, PlusCircle, BarChart4, Eye, Maximize, AlertTriangle, SlidersHorizontal } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { enhanceImagePrompt, createFolder, MediaType, fetchFolders } from "@/services/api";
import { toast } from "sonner";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Input } from "@/components/ui/input";
import { useImageSettings } from "@/context/image-settings-context";
import { useTheme } from "next-themes";
import { useFolderContext } from "@/context/folder-context";

interface ImageOverlayProps {
  onGenerate: (settings: {
    prompt: string;
    model: string;
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
  }) => void;
  isGenerating?: boolean;
  onPromptChange?: (newPrompt: string, isEnhanced: boolean) => void;
  folders?: string[];
  selectedFolder?: string;
  onFolderCreated?: (newFolder: string | string[]) => void;
}

export function ImageOverlay({ 
  onGenerate, 
  isGenerating = false, 
  onPromptChange,
  folders = [],
  selectedFolder = "",
  onFolderCreated
}: ImageOverlayProps) {
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("gpt-image-1");
  const [imageSize, setImageSize] = useState("1024x1024");
  const [saveImages] = useState(true);
  const [mode] = useState("prod");
  const imageSettings = useImageSettings();
  const [aiAnalysisEnabled, setAiAnalysisEnabled] = useState(true);
  const [variations, setVariations] = useState("1");
  const [expanded, setExpanded] = useState(true);
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [isWizardEnhancing, setIsWizardEnhancing] = useState(false);
  const [folder, setFolder] = useState(selectedFolder || "root");
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [isCreatingFolderLoading, setIsCreatingFolderLoading] = useState(false);
  const [isRefreshingFolders, setIsRefreshingFolders] = useState(false);
  const [background, setBackground] = useState("auto");
  const [outputFormat, setOutputFormat] = useState("png");
  const [quality, setQuality] = useState("auto");
  const [inputFidelity, setInputFidelity] = useState("low");
  const [sourceImages, setSourceImages] = useState<File[]>([]);
  const [isClient, setIsClient] = useState(false);
  
  // Reference to the textarea element
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const newFolderInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Add theme context
  const { theme, resolvedTheme } = useTheme();
  const [isDarkTheme, setIsDarkTheme] = useState(false);
  const { refreshFolders } = useFolderContext();
  
  // Move theme detection to useEffect to prevent hydration mismatch
  useEffect(() => {
    // Only run on client-side
    setIsClient(true);
    setIsDarkTheme(
      resolvedTheme === 'dark' || 
      theme === 'dark' || 
      (!theme && !resolvedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)
    );
  }, [theme, resolvedTheme]);

  // Update folder when selectedFolder prop changes
  useEffect(() => {
    setFolder(selectedFolder || "root");
  }, [selectedFolder]);

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

  // Helper function to get model display name for the trigger
  const getModelDisplayName = (modelValue: string) => {
    const modelNames: Record<string, string> = {
      "gpt-image-1": "GPT-Image-1",
      "gpt-image-1.5": "GPT-Image-1.5",
      "gpt-image-1-mini": "GPT-Image-1 Mini"
    };
    return modelNames[modelValue] || modelValue;
  };

  // Get overlay background color based on theme
  const getOverlayBgColor = () => {
    return isDarkTheme 
      ? 'backdrop-blur-md bg-black/70 border-white/10' 
      : 'backdrop-blur-md bg-white/90 border-black/10 shadow-lg';
  };
  
  // Get input and control background color based on theme
  const getControlBgColor = () => {
    return isDarkTheme
      ? 'bg-black/30 border-0 text-white focus:ring-white/20'
      : 'bg-white/50 border-gray-200 text-gray-900 focus:ring-gray-200';
  };
  
  // Get text color based on theme
  const getTextColor = () => {
    return isDarkTheme ? 'text-white' : 'text-gray-900';
  };
  
  // Get muted text color based on theme
  const getMutedTextColor = () => {
    return isDarkTheme ? 'text-white/70' : 'text-gray-500';
  };

  // Get hover background color based on theme
  const getHoverBgColor = () => {
    return isDarkTheme ? 'hover:bg-white/10' : 'hover:bg-gray-200/50';
  };

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
    
    onGenerate({
      prompt,
      model,
      imageSize,
      saveImages,
      mode,
      brandsProtection: imageSettings.settings.brandsProtection,
      brandProtectionModel: "GPT-4o",
      variations: numVariations,
      folder,
      background,
      outputFormat,
      quality,
      inputFidelity,
      sourceImages,
      brandsList: imageSettings.settings.brandsList
    });
  };

  const handleWizardEnhance = async () => {
    if (!prompt.trim() || isGenerating || isWizardEnhancing) return;
    
    // Set loading state
    setIsWizardEnhancing(true);
    
    try {
      // Call the API to enhance the prompt
      const enhancedPrompt = await enhanceImagePrompt(prompt.trim());
      
      // Update the prompt with the enhanced version
      setPrompt(enhancedPrompt);
      
      // Notify parent component about the prompt change
      if (onPromptChange) {
        onPromptChange(enhancedPrompt, true);
      }
      
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
      const result = await createFolder(newFolderName.trim(), MediaType.IMAGE);
      
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
      
      const result = await fetchFolders(MediaType.IMAGE);
      
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
        if (file.size > 25 * 1024 * 1024) {
          toast.error("File too large", {
            description: `${file.name}: Images must be less than 25MB`
          });
          continue;
        }
        
        validFiles.push(file);
      }
      
      // Limit to 5 images total (gpt-image-1 supports up to 10, but we'll be conservative)
      if (sourceImages.length + validFiles.length > 5) {
        toast.warning("Too many images", {
          description: "Maximum 5 images can be selected"
        });
        
        // Take only what we can fit
        const spaceLeft = 5 - sourceImages.length;
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

  return (
    <div className="sticky bottom-0 left-0 right-0 flex items-end justify-center p-6 z-20 pointer-events-none">
      <div className={cn(
        "w-full transition-all duration-300 ease-in-out pointer-events-auto",
        expanded ? "mb-6" : "mb-2"
      )}
      style={{
        maxWidth: isClient && sourceImages.length > 0 ? '58rem' : '56rem' // 4xl = 56rem, so adding just 2rem
      }}>
        <div className={cn(
          "rounded-xl p-4 shadow-lg border",
          getOverlayBgColor()
        )}>
          <div className="flex flex-col space-y-4">
            {/* Image thumbnails row */}
            {isClient && sourceImages.length > 0 && (
              <div className="flex flex-wrap gap-2 items-center">
                {sourceImages.map((img, index) => (
                  <div key={index} className="relative">
                    <div className="relative h-12 w-12">
                      <Image 
                        src={URL.createObjectURL(img)} 
                        alt={`Image ${index + 1}`}
                        fill
                        className={cn(
                          "rounded-md border object-cover transition-all duration-200",
                          index === 0 && sourceImages.length > 1 
                            ? "border-sky-300 ring-2 ring-sky-300/50 shadow-lg shadow-sky-300/25 animate-pulse" 
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
                        isDarkTheme ? "bg-black/70 text-white" : "bg-white/90 text-gray-700"
                      )}
                      disabled={isGenerating}
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
                      getMutedTextColor(),
                      getHoverBgColor()
                    )}
                    disabled={isGenerating}
                  >
                    Clear all
                  </Button>
                )}
              </div>
            )}
            
            {/* Warning for mini model with edit mode */}
            {isClient && sourceImages.length > 0 && model === "gpt-image-1-mini" && (
              <Alert variant="destructive" className="animate-in fade-in-0 slide-in-from-top-2 duration-300">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  GPT-Image-1 Mini does not support image editing. Please switch to GPT-Image-1 or GPT-Image-1.5, or remove source images to use text-to-image generation.
                </AlertDescription>
              </Alert>
            )}
            
            {/* Input row with buttons */}
            <div className="flex items-start gap-3">
              <TooltipProvider>
                <Tooltip delayDuration={300}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setExpanded(!expanded)}
                      aria-label="Toggle options"
                      className={cn(
                        "mt-1",
                        getMutedTextColor(),
                        getHoverBgColor()
                      )}
                      disabled={isGenerating}
                    >
                      {expanded ? (
                        <X className="h-5 w-5" />
                      ) : (
                        <Settings className="h-5 w-5" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="left" className="font-medium">
                    <p>{expanded ? "Hide settings" : "Show settings"}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              
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
                        getMutedTextColor(),
                        getHoverBgColor()
                      )}
                      disabled={isGenerating}
                    >
                      <PlusCircle className="h-5 w-5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="left" className="font-medium">
                    <p>Upload images to edit (max 5)</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                disabled={isGenerating}
                aria-label="Upload image files"
                multiple
              />
              
              <div className="flex-1 relative">
                <Textarea
                  value={prompt}
                  onChange={(e) => {
                    setPrompt(e.target.value);
                    if (onPromptChange) {
                      onPromptChange(e.target.value, false);
                    }
                  }}
                  placeholder={sourceImages.length > 0 ? "Describe how to edit these images..." : "Describe your image..."}
                  className={cn(
                    "border border-gray-500/30 min-h-[40px] max-h-[200px] resize-none px-3 py-2 overflow-y-auto",
                    getControlBgColor(),
                    getTextColor()
                  )}
                  disabled={isGenerating}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && prompt.trim() && !isGenerating) {
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
              
              <div className="flex items-start gap-2 mt-1">
                <TooltipProvider>
                  <Tooltip delayDuration={300}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={handleWizardEnhance}
                        aria-label="Enhance prompt"
                        className={cn(
                          "border-0 min-w-9 h-9",
                          isDarkTheme 
                            ? "bg-white/10 hover:bg-white/20 text-white" 
                            : "bg-gray-100 hover:bg-gray-200 text-gray-900"
                        )}
                        disabled={isGenerating || isWizardEnhancing || !prompt.trim()}
                      >
                        {isWizardEnhancing ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Wand2 className="h-4 w-4" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="left" className="font-medium">
                      <p>Enhance your prompt with AI</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                
                <Button
                  variant="outline"
                  onClick={handleSubmit}
                  className={cn(
                    "border-0",
                    isDarkTheme 
                      ? "bg-white/10 hover:bg-white/20 text-white" 
                      : "bg-gray-100 hover:bg-gray-200 text-gray-900"
                  )}
                  disabled={isGenerating || !prompt.trim() || (sourceImages.length > 0 && model === "gpt-image-1-mini")}
                >
                  {isGenerating ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <ArrowUp className="h-4 w-4 mr-2" />
                  )}
                  {isGenerating ? "Processing..." : sourceImages.length > 0 ? "Edit Images" : "Generate"}
                </Button>
              </div>
            </div>

            {expanded && (
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <TooltipProvider>
                  <div className="flex flex-wrap items-center gap-3 transition-all duration-200 ease-in-out opacity-100 translate-y-0 w-full">
                    {/* Model Selection Dropdown */}
                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <div className="relative">
                          <Select
                            value={model}
                            onValueChange={setModel}
                            disabled={isGenerating}
                          >
                            <SelectTrigger className="w-[180px] h-8">
                              <div className="flex items-center">
                                <Wand2 className="h-4 w-4 mr-2" />
                                <span className="truncate">{getModelDisplayName(model)}</span>
                              </div>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="gpt-image-1">
                                <div className="flex flex-col items-start">
                                  <span className="font-medium">GPT-Image-1</span>
                                  <span className="text-xs text-muted-foreground">Standard quality</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="gpt-image-1.5">
                                <div className="flex flex-col items-start">
                                  <span className="font-medium">GPT-Image-1.5</span>
                                  <span className="text-xs text-muted-foreground">Enhanced, 4x faster</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="gpt-image-1-mini">
                                <div className="flex flex-col items-start">
                                  <span className="font-medium">GPT-Image-1 Mini</span>
                                  <span className="text-xs text-muted-foreground">Economical</span>
                                </div>
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        <p>Select image generation model</p>
                      </TooltipContent>
                    </Tooltip>

                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <div className="relative">
                          <Select
                            value={imageSize}
                            onValueChange={setImageSize}
                            disabled={isGenerating}
                          >
                            <SelectTrigger className="w-[145px] h-8">
                              <div className="flex items-center">
                                <Maximize className="h-4 w-4 mr-2" />
                                <SelectValue placeholder="1024x1024" />
                              </div>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="auto">Auto</SelectItem>
                              <SelectItem value="1024x1024">1024x1024</SelectItem>
                              <SelectItem value="1536x1024">1536x1024</SelectItem>
                              <SelectItem value="1024x1536">1024x1536</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        <p>Select output image dimensions</p>
                      </TooltipContent>
                    </Tooltip>

                    {/* Background Option Dropdown */}
                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <div className="relative">
                          <Select
                            value={background}
                            onValueChange={setBackground}
                            disabled={isGenerating}
                          >
                            <SelectTrigger className="w-[140px] h-8">
                              <div className="flex items-center">
                                <Layers className="h-4 w-4 mr-2" />
                                <SelectValue placeholder="Background" />
                              </div>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="auto">Auto</SelectItem>
                              <SelectItem value="transparent">Transparent</SelectItem>
                              <SelectItem value="opaque">Opaque</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        <p>Choose background transparency type</p>
                      </TooltipContent>
                    </Tooltip>

                    {/* Output Format Dropdown */}
                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <div className="relative">
                          <Select
                            value={outputFormat}
                            onValueChange={setOutputFormat}
                            disabled={isGenerating}
                          >
                            <SelectTrigger className="w-[100px] h-8">
                              <div className="flex items-center">
                                <FileType className="h-4 w-4 mr-2" />
                                <SelectValue placeholder="Format" />
                              </div>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="png">PNG</SelectItem>
                              <SelectItem value="jpeg" disabled={background === "transparent"}>
                                JPEG {background === "transparent" && <span className="text-xs text-muted-foreground ml-1">(requires opaque bg)</span>}
                              </SelectItem>
                              <SelectItem value="webp">WebP</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        <p>Select image file format</p>
                      </TooltipContent>
                    </Tooltip>

                    {/* Quality Dropdown - New */}
                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <div className="relative">
                          <Select
                            value={quality}
                            onValueChange={setQuality}
                            disabled={isGenerating}
                          >
                            <SelectTrigger className="w-[120px] h-8">
                              <div className="flex items-center">
                                <BarChart4 className="h-4 w-4 mr-2" />
                                <SelectValue placeholder="Quality" />
                              </div>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="auto">Auto</SelectItem>
                              <SelectItem value="low">Low</SelectItem>
                              <SelectItem value="medium">Medium</SelectItem>
                              <SelectItem value="high">High</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        <p>Select image quality</p>
                      </TooltipContent>
                    </Tooltip>

                    {/* Input Fidelity Dropdown - Only show when editing images */}
                    {isClient && sourceImages.length > 0 && (
                      <Tooltip delayDuration={300}>
                        <TooltipTrigger asChild>
                          <div className="relative animate-in fade-in-0 slide-in-from-left-2 duration-300">
                            <Select
                              value={inputFidelity}
                              onValueChange={setInputFidelity}
                              disabled={isGenerating}
                            >
                              <SelectTrigger className="w-[100px] h-8">
                                <div className="flex items-center">
                                  <Layers className="h-4 w-4 mr-2" />
                                  <SelectValue placeholder="Fidelity" />
                                </div>
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="low">Low</SelectItem>
                                <SelectItem value="high">High</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="font-medium">
                          <p>Input fidelity for image editing - High provides better reproduction of the highlighted image with blue frame</p>
                        </TooltipContent>
                      </Tooltip>
                    )}

                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <div className="relative">
                          <Select
                            value={variations}
                            onValueChange={setVariations}
                            disabled={isGenerating}
                          >
                            <SelectTrigger className="w-[80px] h-8">
                              <div className="flex items-center">
                                <Images className="h-4 w-4 mr-2" />
                                <SelectValue placeholder="1" />
                              </div>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="1">1</SelectItem>
                              <SelectItem value="2">2</SelectItem>
                              <SelectItem value="3">3</SelectItem>
                              <SelectItem value="4">4</SelectItem>
                              <SelectItem value="5">5</SelectItem>
                              <SelectItem value="6">6</SelectItem>
                              <SelectItem value="7">7</SelectItem>
                              <SelectItem value="8">8</SelectItem>
                              <SelectItem value="9">9</SelectItem>
                              <SelectItem value="10">10</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        <p>Number of image variations to generate</p>
                      </TooltipContent>
                    </Tooltip>

                    {/* Advanced Settings Toggle Button */}
                    <Tooltip delayDuration={300}>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
                          className={cn(
                            "h-8 w-8 rounded-md",
                            showAdvancedSettings && "bg-primary/10"
                          )}
                          disabled={isGenerating}
                        >
                          <SlidersHorizontal className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="font-medium">
                        <p>Toggle advanced settings</p>
                      </TooltipContent>
                    </Tooltip>

                    {/* Advanced Settings - Folder & Analysis */}
                    {showAdvancedSettings && (
                      <>
                        {/* Folder Select Dropdown */}
                        <Tooltip delayDuration={300}>
                          <TooltipTrigger asChild>
                            <div className="relative animate-in fade-in-0 slide-in-from-left-2 duration-300">
                          <Select
                            value={folder}
                            onValueChange={setFolder}
                            disabled={isGenerating}
                            onOpenChange={(open) => {
                              if (!open) {
                                setIsCreatingFolder(false);
                                setNewFolderName("");
                              }
                            }}
                          >
                            <SelectTrigger className="w-[130px] h-8">
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
                                  >
                                    {isCreatingFolderLoading ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
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
                                    >
                                      <RefreshCw className={`h-3 w-3 ${isRefreshingFolders ? 'animate-spin' : ''}`} />
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
                          disabled={isGenerating}
                        >
                          <ToggleGroupItem 
                            value="analyze" 
                            aria-label="Toggle analysis"
                            className={cn(
                              "rounded-md",
                              isDarkTheme ? "bg-black/30 border-0 text-white" : "bg-white/50 border-gray-200 text-gray-900"
                            )}
                            style={{
                              backgroundColor: aiAnalysisEnabled 
                                ? (isDarkTheme ? "rgba(255, 255, 255, 0.15)" : "rgba(209, 213, 219, 0.5)") 
                                : (isDarkTheme ? "rgba(0, 0, 0, 0.3)" : "rgba(255, 255, 255, 0.5)"),
                              border: aiAnalysisEnabled 
                                ? (isDarkTheme ? "1px solid rgba(255, 255, 255, 0.3)" : "1px solid rgba(209, 213, 219, 0.5)") 
                                : (isDarkTheme ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(229, 231, 235, 0.5)"),
                              color: aiAnalysisEnabled 
                                ? (isDarkTheme ? "white" : "rgb(17, 24, 39)") 
                                : (isDarkTheme ? "rgba(255, 255, 255, 0.6)" : "rgb(107, 114, 128)"),
                              padding: "0.5rem",
                              minWidth: "auto",
                              width: "40px",
                              height: "32px",
                              display: "flex",
                              justifyContent: "center",
                              alignItems: "center"
                            }}
                          >
                            <Eye className={`h-4 w-4 ${aiAnalysisEnabled ? (isDarkTheme ? "text-white" : "text-gray-900") : ""}`} />
                          </ToggleGroupItem>
                        </ToggleGroup>
                      </TooltipTrigger>
                      <TooltipContent side="left" className="font-medium">
                        <p>Analyze images for automatic tagging and summary</p>
                      </TooltipContent>
                    </Tooltip>
                      </>
                    )}
                  </div>
                </TooltipProvider>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 
