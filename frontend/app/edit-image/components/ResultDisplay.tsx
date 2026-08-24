'use client';

import React, { useState, useEffect } from 'react';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { DownloadIcon, SaveIcon, ImageIcon, FolderTree, Plus, Check, RefreshCw, Loader2, ArrowRightIcon } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { fetchFolders, createFolder } from '@/services/api';
import { toast } from 'sonner';

interface ResultDisplayProps {
  originalImage: {
    file: File;
    url: string;
    width: number;
    height: number;
  };
  resultData: {
    imageUrl: string;
    model: string;
    prompt: string;
    tokenUsage?: {
      total: number;
      input: number;
      output: number;
    } | null;
  };
  onReset: () => void;
  onSave: (folder?: string) => Promise<void>;
}

export default function ResultDisplay({
  originalImage,
  resultData,
  onSave
}: ResultDisplayProps) {
  const [activeTab, setActiveTab] = useState('result');
  const [isSaving, setIsSaving] = useState(false);
  const [folders, setFolders] = useState<string[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>("root");
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [isCreatingFolderLoading, setIsCreatingFolderLoading] = useState(false);
  const [isRefreshingFolders, setIsRefreshingFolders] = useState(false);
  const newFolderInputRef = React.useRef<HTMLInputElement>(null);
  const aspectRatio = originalImage.height ? originalImage.width / originalImage.height : 1;

  // Fetch available folders when component mounts
  useEffect(() => {
    const loadFolders = async () => {
      try {
        setIsRefreshingFolders(true);
        const result = await fetchFolders();
        setFolders(result.folders);
      } catch (error) {
        console.error("Error loading folders:", error);
        toast.error("Error loading folders", {
          description: "Failed to load folders from the gallery"
        });
      } finally {
        setIsRefreshingFolders(false);
      }
    };

    loadFolders();
  }, []);

  // Focus the new folder input when creating folder
  useEffect(() => {
    if (isCreatingFolder && newFolderInputRef.current) {
      newFolderInputRef.current.focus();
    }
  }, [isCreatingFolder]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleCreateFolder();
    } else if (e.key === 'Escape') {
      setIsCreatingFolder(false);
      setNewFolderName("");
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;

    setIsCreatingFolderLoading(true);
    try {
      await createFolder(newFolderName.trim());

      // Refresh folders
      const result = await fetchFolders();
      setFolders(result.folders);

      // Select the newly created folder
      setSelectedFolder(newFolderName.trim());

      // Reset state
      setIsCreatingFolder(false);
      setNewFolderName("");

      toast.success("Folder created", {
        description: `Folder "${newFolderName.trim()}" has been created`
      });
    } catch (error) {
      console.error("Error creating folder:", error);
      toast.error("Error creating folder", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
    } finally {
      setIsCreatingFolderLoading(false);
    }
  };

  const handleRefreshFolders = async () => {
    setIsRefreshingFolders(true);
    try {
      const result = await fetchFolders();
      setFolders(result.folders);
      toast.success("Folders refreshed");
    } catch (error) {
      console.error("Error refreshing folders:", error);
      toast.error("Error refreshing folders", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
    } finally {
      setIsRefreshingFolders(false);
    }
  };

  const handleDownload = () => {
    // Create an anchor element and trigger download
    const a = document.createElement('a');
    a.href = resultData.imageUrl;
    a.download = `edited_${originalImage.file.name}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Pass the selected folder to the onSave function
      // If root folder is selected, pass empty string
      await onSave(selectedFolder === "root" ? "" : selectedFolder);
      toast.success("Image saved", {
        description: selectedFolder === "root" 
          ? "Image has been saved to root folder" 
          : `Image has been saved to folder: ${selectedFolder}`
      });
    } catch (error) {
      console.error('Error saving image:', error);
      toast.error("Error saving image", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-6">
          <TabsTrigger value="result" className="flex items-center gap-2">
            <ImageIcon className="h-4 w-4" />
            Result
          </TabsTrigger>
          <TabsTrigger value="comparison" className="flex items-center gap-2">
            <ImageIcon className="h-4 w-4" />
            Comparison
          </TabsTrigger>
        </TabsList>

        <TabsContent value="result" className="mt-0">
          <Card className="p-6 flex flex-col items-center justify-center border-0 shadow-none">
            <div className="w-full max-w-2xl">
              <div className="relative w-full" style={{ aspectRatio }}>
                <Image 
                  src={resultData.imageUrl}
                  alt="Generated result"
                  fill
                  className="object-contain rounded-lg shadow-md"
                  sizes="(max-width: 768px) 100vw, 50vw"
                  unoptimized
                />
              </div>
            </div>

            <div className="w-full max-w-2xl mt-4 space-y-2">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{resultData.model}</Badge>
                {resultData.tokenUsage && (
                  <Badge variant="outline">{resultData.tokenUsage.total} tokens</Badge>
                )}
              </div>

              <div className="text-sm text-muted-foreground mt-1">
                <p><strong>Prompt:</strong> {resultData.prompt}</p>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="comparison" className="mt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 relative">
            <Card className="p-4 flex flex-col items-center border-0 shadow-none">
              <div className="relative w-full flex items-center justify-center bg-muted/30 rounded-lg overflow-hidden p-2">
                <div className="relative w-full" style={{ aspectRatio }}>
                  <Image 
                    src={originalImage.url}
                    alt="Original"
                    fill
                    className="object-contain rounded-lg"
                    sizes="(max-width: 768px) 100vw, 40vw"
                    unoptimized
                  />
                </div>
              </div>
            </Card>

            {/* Arrow pointing to generated image */}
            <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10 hidden sm:flex items-center justify-center">
              <div className="bg-primary/10 backdrop-blur-sm rounded-full p-2">
                <ArrowRightIcon className="h-6 w-6 text-primary" />
              </div>
            </div>

            <Card className="p-4 flex flex-col items-center border-0 shadow-none">
              <div className="relative w-full flex items-center justify-center bg-muted/30 rounded-lg overflow-hidden p-2">
                <div className="relative w-full" style={{ aspectRatio }}>
                  <Image 
                    src={resultData.imageUrl}
                    alt="Generated"
                    fill
                    className="object-contain rounded-lg"
                    sizes="(max-width: 768px) 100vw, 40vw"
                    unoptimized
                  />
                </div>
              </div>
            </Card>
          </div>

          <div className="mt-4 p-4 bg-muted/20 rounded-md">
            <p className="text-sm text-muted-foreground"><strong>Prompt:</strong> {resultData.prompt}</p>

            {resultData.tokenUsage && (
              <div className="mt-2 text-xs text-muted-foreground grid grid-cols-3 gap-2">
                <div>
                  <p>Total Tokens</p>
                  <p className="font-mono">{resultData.tokenUsage.total}</p>
                </div>
                <div>
                  <p>Input Tokens</p>
                  <p className="font-mono">{resultData.tokenUsage.input}</p>
                </div>
                <div>
                  <p>Output Tokens</p>
                  <p className="font-mono">{resultData.tokenUsage.output}</p>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      <div className="flex flex-wrap gap-2 mt-4">
        <Button 
          variant="outline" 
          onClick={handleDownload}
          className="gap-2"
        >
          <DownloadIcon className="h-4 w-4" />
          Download
        </Button>
        
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="relative">
                <Select
                  value={selectedFolder}
                  onValueChange={setSelectedFolder}
                  disabled={isSaving}
                  onOpenChange={(open) => {
                    if (!open) {
                      setIsCreatingFolder(false);
                      setNewFolderName("");
                    }
                  }}
                >
                  <SelectTrigger className="w-[180px] h-9">
                    <div className="flex items-center">
                      <FolderTree className="h-4 w-4 mr-2 text-primary" />
                      <SelectValue placeholder="Root folder" />
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

                    <SelectItem value="root">Root folder</SelectItem>
                    {folders.map((folderPath) => (
                      <SelectItem key={folderPath} value={folderPath}>
                        {folderPath}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>Select folder to save image</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <Button 
          onClick={handleSave}
          className="gap-2"
          disabled={isSaving}
        >
          <SaveIcon className="h-4 w-4" />
          {isSaving ? 'Saving...' : 'Save to Gallery'}
        </Button>
      </div>
    </div>
  );
}
