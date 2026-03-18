import { useState, useRef } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Upload, X, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";

interface ImageUploaderProps {
  onImageSelected: (image: File | null) => void;
  disabled?: boolean;
}

export function ImageUploader({ onImageSelected, disabled = false }: ImageUploaderProps) {
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    
    if (file) {
      // Check file type
      if (!file.type.match('image/(jpeg|png|webp)')) {
        toast.error("Invalid file type", {
          description: "Please select a JPG, PNG, or WebP image"
        });
        return;
      }
      
      // Check file size (25MB max for gpt-image-1.5)
      if (file.size > 25 * 1024 * 1024) {
        toast.error("File too large", {
          description: "Image must be less than 25MB"
        });
        return;
      }
      
      // Create preview URL
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      setSelectedImage(file);
      onImageSelected(file);
      
      toast.success("Image selected", {
        description: `${file.name} (${(file.size / 1024 / 1024).toFixed(2)}MB)`
      });
    } else {
      setPreviewUrl(null);
      setSelectedImage(null);
      onImageSelected(null);
    }
  };

  const handleRemoveImage = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setSelectedImage(null);
    onImageSelected(null);
    
    // Reset the file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleUploadClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className="flex flex-col items-center space-y-2">
      {previewUrl ? (
        <div className="relative h-16 w-16">
          <Image 
            src={previewUrl} 
            alt="Selected image" 
            fill
            className="rounded-md border border-gray-500/30 object-cover"
            sizes="64px"
            unoptimized
          />
          <button 
            onClick={handleRemoveImage}
            className="absolute -top-2 -right-2 bg-black/70 rounded-full p-0.5 text-white hover:bg-black"
            disabled={disabled}
            aria-label="Remove selected image"
            title="Remove image"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <div 
          className="w-16 h-16 flex items-center justify-center rounded-md border border-dashed border-gray-500/30 cursor-pointer hover:bg-gray-700/20"
          onClick={handleUploadClick}
          role="button"
          aria-label="Select an image"
          title="Click to select an image"
        >
          <ImageIcon className="h-6 w-6 text-gray-400" />
        </div>
      )}
      
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleImageSelect}
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        disabled={disabled}
        aria-label="Upload image file"
        title="Upload image"
      />
      
      <Button 
        variant="outline" 
        size="sm" 
        onClick={handleUploadClick}
        className="bg-black/30 border-gray-500/30 text-white hover:bg-white/10 hover:text-white text-xs px-2 h-7"
        disabled={disabled}
      >
        <Upload className="h-3 w-3 mr-1" />
        {selectedImage ? "Change" : "Select Image"}
      </Button>
    </div>
  );
} 
