"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ImageOverlay } from "./ImageOverlay";
import { useImageJobs } from "@/context/image-jobs-context";
import { formatImageJobError } from "@/types/image-jobs";
import { cn } from "@/utils/utils";
import {
  editImage,
  fetchFolders,
  PipelineAction,
  protectImagePrompt,
  saveGeneratedImages,
  type ImagePipelineRequest,
} from "@/services/api";

interface ImageCreationContainerProps {
  className?: string;
  initialFolder?: string;
  onImagesSaved?: (count?: number) => void;
}

interface ImageGenerationSettings {
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
}

function formatImageCount(count: number): string {
  return `${count} image${count === 1 ? "" : "s"}`;
}

function createIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `image-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function ImageCreationContainer({
  className = "",
  initialFolder = "root",
  onImagesSaved,
}: ImageCreationContainerProps) {
  const { submitJob } = useImageJobs();
  const [isEditing, setIsEditing] = useState(false);
  const [folders, setFolders] = useState<string[]>([]);
  const [selectedFolder, setSelectedFolder] = useState(initialFolder || "root");
  const editInFlightRef = useRef(false);

  useEffect(() => {
    setSelectedFolder(initialFolder || "root");
  }, [initialFolder]);

  useEffect(() => {
    const loadFolders = async () => {
      try {
        const result = await fetchFolders();
        setFolders(result.folders);
      } catch (error) {
        console.error("Error loading folders:", error);
      }
    };
    void loadFolders();
  }, []);

  const protectPrompt = async (settings: ImageGenerationSettings): Promise<{
    prompt: string;
    applied: boolean;
  }> => {
    const brands = settings.brandsList ?? [];
    if (settings.brandsProtection === "off" || brands.length === 0) {
      return { prompt: settings.prompt, applied: false };
    }

    try {
      const prompt = await protectImagePrompt(
        settings.prompt,
        brands,
        settings.brandsProtection,
      );
      return { prompt, applied: prompt !== settings.prompt };
    } catch (error) {
      console.error("Error applying brand protection:", error);
      toast.warning("Brand protection could not be applied", {
        description: "The original prompt will be used.",
      });
      return { prompt: settings.prompt, applied: false };
    }
  };

  const runExistingEditFlow = async (
    settings: ImageGenerationSettings,
    generationPrompt: string,
    brandProtectionApplied: boolean,
  ) => {
    const sourceImages = settings.sourceImages ?? [];
    const normalizedFolder = settings.folder === "root" ? "" : settings.folder;
    const toastId = toast.loading("Editing images…", {
      description: `Processing ${formatImageCount(sourceImages.length)}`,
    });

    try {
      const response = await editImage(
        sourceImages,
        generationPrompt,
        settings.variations,
        settings.imageSize,
        settings.quality,
        settings.inputFidelity,
        settings.model,
        settings.outputFormat,
        settings.background,
      );

      const existingMetadata =
        response.metadata &&
        typeof response.metadata === "object" &&
        !Array.isArray(response.metadata)
          ? (response.metadata as Record<string, unknown>)
          : {};
      const responseToSave = brandProtectionApplied
        ? {
            ...response,
            metadata: {
              ...existingMetadata,
              brand_protection_mode: settings.brandsProtection,
              protected_brands: (settings.brandsList ?? []).join(", "),
              protected_prompt: generationPrompt,
            },
          }
        : response;

      const saveResponse = await saveGeneratedImages(
        responseToSave,
        settings.prompt,
        true,
        normalizedFolder,
        settings.outputFormat,
        settings.model,
        settings.background,
        settings.imageSize,
        settings.analyze,
      );

      toast.success(`${formatImageCount(saveResponse.total_saved)} ready`, {
        id: toastId,
        description: normalizedFolder
          ? `Saved to ${normalizedFolder}`
          : "Saved to the root gallery",
      });
      onImagesSaved?.(saveResponse.total_saved);
    } catch (error) {
      toast.error("Image editing failed", {
        id: toastId,
        description: error instanceof Error ? error.message : "Unknown error occurred",
      });
      throw error;
    }
  };

  const handleGenerate = async (settings: ImageGenerationSettings) => {
    const hasSourceImages = (settings.sourceImages?.length ?? 0) > 0;
    if (hasSourceImages && editInFlightRef.current) return;
    if (hasSourceImages) {
      editInFlightRef.current = true;
      setIsEditing(true);
    }

    try {
      const normalizedFolder = settings.folder === "root" ? "" : settings.folder;
      const protectedPrompt = await protectPrompt(settings);

      if (hasSourceImages) {
        await runExistingEditFlow(
          settings,
          protectedPrompt.prompt,
          protectedPrompt.applied,
        );
        return;
      }

      const metadata: Record<string, unknown> = {
        original_prompt: settings.prompt,
      };
      if (protectedPrompt.applied) {
        metadata.brand_protection_mode = settings.brandsProtection;
        metadata.protected_brands = settings.brandsList ?? [];
        metadata.protected_prompt = protectedPrompt.prompt;
      }

      const request: ImagePipelineRequest = {
        action: PipelineAction.GENERATE,
        prompt: protectedPrompt.prompt,
        model: settings.model,
        n: settings.variations,
        size: settings.imageSize,
        response_format: "b64_json",
        quality: settings.quality,
        output_format: settings.outputFormat,
        background: settings.background,
        save_options: {
          enabled: true,
          save_all: true,
          folder_path: normalizedFolder,
          output_format: settings.outputFormat,
          background: settings.background,
          metadata,
        },
        analysis_options: {
          enabled: settings.analyze,
        },
        metadata,
      };

      const submissionId = createIdempotencyKey();

      const job = await submitJob(
        request,
        submissionId,
        submissionId,
      );
      toast.success("Added to generation queue", {
        description: `${formatImageCount(job.requested_images)} will appear here as they finish.`,
      });
    } catch (error) {
      console.error("Error starting image operation:", error);
      if (!hasSourceImages) {
        toast.error("Could not start image generation", {
          description:
            formatImageJobError(error instanceof Error ? error.message : null) ??
            "Unknown error occurred",
        });
      }
    } finally {
      if (hasSourceImages) {
        editInFlightRef.current = false;
        setIsEditing(false);
      }
    }
  };

  const handleFolderCreated = (newFolder: string | string[]) => {
    setFolders((current) => {
      const additions = Array.isArray(newFolder) ? newFolder : [newFolder];
      return Array.from(new Set([...current, ...additions])).sort((a, b) =>
        a.localeCompare(b),
      );
    });
    if (!Array.isArray(newFolder)) setSelectedFolder(newFolder);
  };

  return (
    <div className={cn("relative h-full w-full", className)}>
      <ImageOverlay
        onGenerate={handleGenerate}
        isSubmitting={isEditing}
        folders={folders}
        selectedFolder={selectedFolder}
        onFolderCreated={handleFolderCreated}
      />
    </div>
  );
}
