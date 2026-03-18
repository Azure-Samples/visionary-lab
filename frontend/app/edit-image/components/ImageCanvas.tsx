'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { 
  Paintbrush, 
  Eraser, 
  UndoIcon,
  RedoIcon,
  KeyboardIcon,
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Slider } from '@/components/ui/slider';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import GenerateForm from './GenerateForm';

// Tool types for drawing
type DrawingTool = 'brush' | 'eraser';
// Drawing action for history
type DrawingAction = {
  type: 'draw' | 'clear';
  data?: ImageData;
};

interface ImageCanvasProps {
  image: {
    file: File;
    url: string;
    width: number;
    height: number;
  };
  onProceed: (maskCanvas: HTMLCanvasElement, formData: FormData) => void;
}

export default function ImageCanvas({ image, onProceed }: ImageCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const maskCanvasRef = useRef<HTMLCanvasElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [currentTool, setCurrentTool] = useState<DrawingTool>('brush');
  const [brushSize, setBrushSize] = useState(30);
  const [showMask, setShowMask] = useState(true);
  const [history, setHistory] = useState<DrawingAction[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [isDrawing, setIsDrawing] = useState(false);
  const [lastPosition, setLastPosition] = useState<{ x: number; y: number } | null>(null);
  
  // Create a mask canvas with the EXACT same dimensions as the original image
  const apiMaskCanvasRef = useRef<HTMLCanvasElement | null>(null);
  
  // Initialize the API mask canvas with the original image dimensions
  useEffect(() => {
    if (!image) return;
    
    // Create the API mask canvas if it doesn't exist
    if (!apiMaskCanvasRef.current) {
      apiMaskCanvasRef.current = document.createElement('canvas');
    }
    
    // Set the dimensions to match the original image
    apiMaskCanvasRef.current.width = image.width;
    apiMaskCanvasRef.current.height = image.height;
    
    // Initialize with transparent (areas to edit) - INVERTED LOGIC
    const ctx = apiMaskCanvasRef.current.getContext('2d', { willReadFrequently: true });
    if (ctx) {
      ctx.clearRect(0, 0, image.width, image.height);
    }
  }, [image]);
  
  // Calculate dimensions for the canvas based on the image and available space
  useEffect(() => {
    if (!image) return;
    
    // Log original image dimensions
    console.log("Original image loaded:", image.width, "x", image.height, 
                "Aspect ratio:", (image.width / image.height).toFixed(2));
    
    // Get the maximum width within the container
    const maxWidth = Math.min(window.innerWidth - 100, 800);
    const maxHeight = 600;
    
    // Calculate the aspect ratio
    const aspectRatio = image.width / image.height;
    
    // Calculate the dimensions respecting aspect ratio
    let width = maxWidth;
    let height = width / aspectRatio;
    
    // If height exceeds maxHeight, adjust accordingly
    if (height > maxHeight) {
      height = maxHeight;
      width = height * aspectRatio;
    }
    
    // Ensure dimensions are integers
    width = Math.floor(width);
    height = Math.floor(height);
    
    console.log("Display canvas dimensions:", width, "x", height);
    
    setDimensions({
      width: width,
      height: height
    });
  }, [image]);
  
  // Draw the image on the canvas
  useEffect(() => {
    if (!canvasRef.current || !maskCanvasRef.current || !image || dimensions.width === 0) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return;
    
    // Set canvas dimensions
    canvas.width = dimensions.width;
    canvas.height = dimensions.height;
    
    // Set mask canvas dimensions
    const maskCanvas = maskCanvasRef.current;
    const maskCtx = maskCanvas.getContext('2d', { willReadFrequently: true });
    
    if (!maskCtx) return;
    
    maskCanvas.width = dimensions.width;
    maskCanvas.height = dimensions.height;
    
    // Clear mask
    maskCtx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    
    // Create an image element to draw
    const img = new Image();
    img.onload = () => {
      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // Draw image
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      
      // Save initial state
      setHistory([{ type: 'clear' }]);
      setHistoryIndex(0);
    };
    img.src = image.url;
  }, [image, dimensions]);

  // Update the debug mask preview whenever the mask canvas changes
  const updateDebugMaskPreview = useCallback(() => {
    if (!apiMaskCanvasRef.current) return;
    
    try {
      // Create a data URL from the API mask canvas
      const maskUrl = apiMaskCanvasRef.current.toDataURL('image/png');
      if (maskUrl) {
        console.log("Debug mask URL:", maskUrl);
      }
    } catch (e) {
      console.error("Error creating debug mask URL:", e);
    }
  }, []);
  
  // Update the API mask canvas based on drawing
  const updateApiMask = useCallback((prevX: number, prevY: number, x: number, y: number) => {
    if (!apiMaskCanvasRef.current || !maskCanvasRef.current || !image) return;
    
    const displayCanvas = maskCanvasRef.current;
    const apiCanvas = apiMaskCanvasRef.current;
    
    // Calculate the scale factors between display canvas and original image
    const scaleX = image.width / displayCanvas.width;
    const scaleY = image.height / displayCanvas.height;
    
    // Convert the coordinates to the API mask canvas scale
    const apiX1 = prevX * scaleX;
    const apiY1 = prevY * scaleY;
    const apiX2 = x * scaleX;
    const apiY2 = y * scaleY;
    
    // Get the API mask context
    const apiCtx = apiCanvas.getContext('2d', { willReadFrequently: true });
    if (!apiCtx) return;
    
    // Set drawing properties
    apiCtx.lineJoin = 'round';
    apiCtx.lineCap = 'round';
    apiCtx.lineWidth = brushSize * Math.max(scaleX, scaleY); // Scale brush size
    
    if (currentTool === 'brush') {
      // For brush: make the drawn areas opaque black (to be preserved)
      apiCtx.globalCompositeOperation = 'source-over';
      apiCtx.strokeStyle = '#000000';
    } else {
      // For eraser: make the erased areas transparent (to be edited)
      apiCtx.globalCompositeOperation = 'destination-out';
      apiCtx.strokeStyle = 'rgba(255,255,255,1)'; // Color doesn't matter, we're erasing
    }
    
    // Draw the line
    apiCtx.beginPath();
    apiCtx.moveTo(apiX1, apiY1);
    apiCtx.lineTo(apiX2, apiY2);
    apiCtx.stroke();
  }, [image, brushSize, currentTool]);
  
  // Utility function to update the API mask from the display mask
  const updateApiMaskFromDisplay = useCallback(() => {
    if (!maskCanvasRef.current || !apiMaskCanvasRef.current) return;
    
    // ... rest of function implementation ...
  }, []);

  // Drawing functions
  const startDrawing = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!maskCanvasRef.current) return;
    
    const canvas = maskCanvasRef.current;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return;
    
    // Save the current canvas state for undo
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    
    // Only add to history if we're starting a new action
    if (historyIndex < history.length - 1) {
      // If we're in the middle of the history, remove all future actions
      setHistory(history.slice(0, historyIndex + 1));
    }
    
    // Add current state to history
    setHistory([...history, { type: 'draw', data: imageData }]);
    setHistoryIndex(historyIndex + 1);
    
    // Set drawing properties
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    
    // Different visual handling for brush vs eraser
    if (currentTool === 'brush') {
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = 'rgba(255,255,255,1)';
    } else {
      // For eraser, we need to visually erase by using destination-out
      ctx.globalCompositeOperation = 'destination-out';
      ctx.strokeStyle = 'rgba(255,255,255,1)'; // Color doesn't matter for eraser
    }
    
    ctx.lineWidth = brushSize;
    
    // Get the mouse position relative to the canvas
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top) * (canvas.height / rect.height);
    
    // Start a new path
    ctx.beginPath();
    ctx.moveTo(x, y);
    
    // Also update the API mask canvas
    updateApiMask(x, y, x, y);
    
    setIsDrawing(true);
    setLastPosition({ x, y });
  }, [history, historyIndex, currentTool, brushSize, updateApiMask]);
  
  const draw = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !maskCanvasRef.current || !lastPosition) return;
    
    const canvas = maskCanvasRef.current;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return;
    
    // Get the mouse position relative to the canvas
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top) * (canvas.height / rect.height);
    
    // Continue the path from the last position
    ctx.beginPath();
    ctx.moveTo(lastPosition.x, lastPosition.y);
    ctx.lineTo(x, y);
    ctx.stroke();
    
    // Also update the API mask canvas
    updateApiMask(lastPosition.x, lastPosition.y, x, y);
    
    setLastPosition({ x, y });
  }, [isDrawing, lastPosition, updateApiMask]);
  
  const stopDrawing = useCallback(() => {
    setIsDrawing(false);
    
    // Update the debug mask preview
    updateDebugMaskPreview();
  }, [updateDebugMaskPreview]);

  // Define functions with useCallback to prevent unnecessary recreation
  const clearCanvas = useCallback(() => {
    if (!maskCanvasRef.current) return;
    
    const canvas = maskCanvasRef.current;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return;
    
    // Clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Clear the API mask canvas too
    if (apiMaskCanvasRef.current) {
      const apiCtx = apiMaskCanvasRef.current.getContext('2d');
      if (apiCtx) {
        apiCtx.clearRect(0, 0, apiMaskCanvasRef.current.width, apiMaskCanvasRef.current.height);
      }
    }
    
    // Add the clear action to history
    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push({ type: 'clear' });
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
    
    // Update the debug mask preview
    updateDebugMaskPreview();
  }, [history, historyIndex, updateDebugMaskPreview]);

  const handleUndo = useCallback(() => {
    if (historyIndex <= 0 || !maskCanvasRef.current) {
      console.log("Nothing to undo");
      return;
    }
    
    console.log("Undoing. History index:", historyIndex);
    
    const canvas = maskCanvasRef.current;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return;
    
    // If current state is a draw action with saved data, go back to previous state
    const newHistoryIndex = historyIndex - 1;
    const prevAction = history[newHistoryIndex];
    
    // Clear the canvas first
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // If the previous state has an image, restore it
    if (prevAction.data) {
      ctx.putImageData(prevAction.data, 0, 0);
    }
    
    // Update history index
    setHistoryIndex(newHistoryIndex);
    
    // Update the API mask and debug preview
    updateApiMaskFromDisplay();
    updateDebugMaskPreview();
  }, [history, historyIndex, updateApiMaskFromDisplay, updateDebugMaskPreview]);

  const handleRedo = useCallback(() => {
    if (historyIndex >= history.length - 1 || !maskCanvasRef.current) {
      console.log("Nothing to redo");
      return;
    }
    
    console.log("Redoing. History index:", historyIndex);
    
    const canvas = maskCanvasRef.current;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return;
    
    // Move forward in history
    const newHistoryIndex = historyIndex + 1;
    const nextAction = history[newHistoryIndex];
    
    // Clear the canvas first
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // If the next state has an image, restore it
    if (nextAction.data) {
      ctx.putImageData(nextAction.data, 0, 0);
    }
    
    // Update history index
    setHistoryIndex(newHistoryIndex);
    
    // Update the API mask and debug preview
    updateApiMaskFromDisplay();
    updateDebugMaskPreview();
  }, [history, historyIndex, updateApiMaskFromDisplay, updateDebugMaskPreview]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Prevent shortcut activation when typing in input fields
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      
      switch (e.key.toLowerCase()) {
        case 'b': // Brush tool
          setCurrentTool('brush');
          break;
        case 'e': // Eraser tool
          setCurrentTool('eraser');
          break;
        case 'z': // Undo
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            if (e.shiftKey) {
              // Redo with Ctrl+Shift+Z or Cmd+Shift+Z
              handleRedo();
            } else {
              // Undo with Ctrl+Z or Cmd+Z
              handleUndo();
            }
          }
          break;
        case 'y': // Redo with Ctrl+Y or Cmd+Y
          if ((e.ctrlKey || e.metaKey) && !e.shiftKey) {
            e.preventDefault();
            handleRedo();
          }
          break;
        case 'escape': // Clear tutorial
          break;
        case 'delete':
        case 'backspace':
          if (!e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) {
            clearCanvas();
          }
          break;
      }
      
      // Handle number keys 1-9 for brush size
      const num = parseInt(e.key);
      if (!isNaN(num) && num >= 1 && num <= 9) {
        // Map 1-9 to brush sizes 5-45
        setBrushSize(num * 5);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [clearCanvas, handleUndo, handleRedo]);

  // Set up the update debug mask effect
  useEffect(() => {
    // This effect sets up the debug mask preview
    updateDebugMaskPreview();
  }, [updateDebugMaskPreview]);

  // Handle form submission and proceed to next step
  const handleFormSubmit = async (formData: FormData) => {
    if (!maskCanvasRef.current) return;
    
    // Call the onProceed callback with the mask canvas and form data
    onProceed(apiMaskCanvasRef.current!, formData);
  };

  // Toggle mask visibility
  const toggleMaskVisibility = useCallback(() => {
    setShowMask(prev => !prev);
  }, []);

  const getCursorClass = (tool: DrawingTool): string => {
    if (tool === 'brush') return 'cursor-brush';
    if (tool === 'eraser') return 'cursor-eraser';
    return 'cursor-default';
  };

  const getCursorStyle = (tool: DrawingTool, size: number): string => {
    if (tool === 'brush') {
      return `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23ffffff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='${size / 4}' fill='%23ffffff' stroke='%23000000' stroke-width='1'/%3E%3C/svg%3E") 12 12, crosshair`;
    }
    if (tool === 'eraser') {
      return `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23ffffff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='6' y='6' width='12' height='12' fill='%23ffffff' stroke='%23000000' stroke-width='1'/%3E%3C/svg%3E") 12 12, crosshair`;
    }
    return 'default';
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col space-y-2">
        <div className="bg-muted/30 rounded-lg p-1.5 mb-2 flex-shrink-0">
          {/* Single row toolbar with all controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ToggleGroup type="single" value={currentTool} onValueChange={(value) => value && setCurrentTool(value as DrawingTool)}>
                <ToggleGroupItem value="brush" aria-label="Brush tool">
                  <Paintbrush className="h-4 w-4" />
                </ToggleGroupItem>
                <ToggleGroupItem value="eraser" aria-label="Eraser tool">
                  <Eraser className="h-4 w-4" />
                </ToggleGroupItem>
              </ToggleGroup>
              
              <div className="flex items-center gap-2 ml-1">
                <label htmlFor="brush-size" className="text-xs">Size:</label>
                <Slider 
                  id="brush-size"
                  min={1} 
                  max={100} 
                  step={1} 
                  value={[brushSize]} 
                  onValueChange={(value) => setBrushSize(value[0])}
                  className="w-24"
                />
                <span className="text-xs w-10 text-center">{brushSize}px</span>
              </div>
            </div>
            
            <div className="flex items-center gap-1">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleUndo}
                      disabled={historyIndex <= 0}
                    >
                      <UndoIcon className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Undo (Ctrl/Cmd+Z)</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleRedo}
                      disabled={historyIndex >= history.length - 1}
                    >
                      <RedoIcon className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Redo (Ctrl/Cmd+Y)</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={clearCanvas}
                      className="ml-1"
                    >
                      Clear
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Clear mask (Delete)</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={toggleMaskVisibility}
                      className="ml-1"
                    >
                      {showMask ? "Hide Mask" : "Show Mask"}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Toggle mask visibility</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Drawing Canvas */}
          <Card className="relative flex items-center justify-center p-4 overflow-auto bg-muted/20 border-0 shadow-none">
            <div 
              style={{ 
                position: 'relative'
              }}
            >
              {/* Base image canvas */}
              <canvas
                ref={canvasRef}
                width={dimensions.width}
                height={dimensions.height}
                className="max-w-full shadow-md rounded-lg"
              />
              
              {/* Drawing canvas overlay */}
              <canvas
                ref={maskCanvasRef}
                width={dimensions.width}
                height={dimensions.height}
                className={`absolute top-0 left-0 max-w-full ${showMask ? 'opacity-80' : 'opacity-0'} pointer-events-auto z-10 rounded-lg ${
                  getCursorClass(currentTool)
                }`}
                style={{ 
                  mixBlendMode: 'screen',
                  cursor: getCursorStyle(currentTool, brushSize),
                }}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
              />
            </div>
          </Card>
          
          {/* Generate Form */}
          <div className="bg-muted/20 rounded-xl border-0 shadow-none p-4 relative">
            <GenerateForm
              originalImage={image}
              maskCanvas={apiMaskCanvasRef.current || document.createElement('canvas')}
              onSubmit={handleFormSubmit}
            />
            
            <div className="absolute bottom-4 right-4">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex items-center cursor-help">
                      <KeyboardIcon className="h-3 w-3 mr-1" />
                      <span className="text-xs text-muted-foreground">Shortcuts</span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-sm">
                    <div className="space-y-2">
                      <h4 className="font-medium">Keyboard Shortcuts</h4>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                        <div className="flex items-center">
                          <kbd className="px-1.5 py-0.5 bg-secondary border border-border rounded text-xs mr-2 text-secondary-foreground font-medium">B</kbd>
                          <span>Brush tool</span>
                        </div>
                        <div className="flex items-center">
                          <kbd className="px-1.5 py-0.5 bg-secondary border border-border rounded text-xs mr-2 text-secondary-foreground font-medium">E</kbd>
                          <span>Eraser tool</span>
                        </div>
                        <div className="flex items-center">
                          <kbd className="px-1.5 py-0.5 bg-secondary border border-border rounded text-xs mr-2 text-secondary-foreground font-medium">Ctrl+Z</kbd>
                          <span>Undo</span>
                        </div>
                        <div className="flex items-center">
                          <kbd className="px-1.5 py-0.5 bg-secondary border border-border rounded text-xs mr-2 text-secondary-foreground font-medium">Ctrl+Y</kbd>
                          <span>Redo</span>
                        </div>
                        <div className="flex items-center">
                          <kbd className="px-1.5 py-0.5 bg-secondary border border-border rounded text-xs mr-2 text-secondary-foreground font-medium">Delete</kbd>
                          <span>Clear mask</span>
                        </div>
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
