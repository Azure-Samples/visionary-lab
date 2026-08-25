"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  ImageOff,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { OptimizedImage } from "@/components/OptimizedImage";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useImageJobs } from "@/context/image-jobs-context";
import { sasTokenService } from "@/services/sas-token";
import {
  formatImageJobError,
  isFailedImageJob,
  type ImageJobEntry,
  type ImageJobOutput,
  type ImageOutputStatus,
} from "@/types/image-jobs";
import { cn } from "@/utils/cn";

interface ImageJobOutputCardProps {
  job: ImageJobEntry;
  output: ImageJobOutput;
}

const outputLabels: Record<ImageOutputStatus, string> = {
  queued: "Queued",
  generating: "Generating",
  saving: "Saving",
  ready: "Ready",
  failed: "Failed",
  cancelled: "Cancelled",
};

function getAspectRatio(size: string, width?: number, height?: number): number {
  if (width && height) return width / height;
  const [parsedWidth, parsedHeight] = size.split("x").map(Number);
  if (parsedWidth > 0 && parsedHeight > 0) return parsedWidth / parsedHeight;
  return 1;
}

export function ImageJobOutputCard({ job, output }: ImageJobOutputCardProps) {
  const { retryJob, mutationByJobId } = useImageJobs();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState(false);
  const effectiveStatus: ImageOutputStatus = output.status === "ready"
    ? "ready"
    : isFailedImageJob(job.status)
      ? "failed"
      : job.status === "cancelled"
        ? "cancelled"
        : output.status;
  const aspectRatio = useMemo(
    () => getAspectRatio(job.size, output.asset?.width, output.asset?.height),
    [job.size, output.asset?.height, output.asset?.width],
  );
  const asset = output.asset;
  const mutation = mutationByJobId[job.id];
  const firstFailedOutput = job.outputs.find((item) => item.status === "failed");
  const canRetry = job.status === "partial"
    ? output.status === "failed" && output.index === firstFailedOutput?.index
    : output.index === 1 &&
      (isFailedImageJob(job.status) || job.status === "cancelled");
  const failedOutputCount = job.outputs.filter((item) => item.status === "failed").length;
  const failureCount = Math.max(
    failedOutputCount,
    job.failed_images,
    isFailedImageJob(job.status) ? job.requested_images : 0,
    1,
  );
  const rawError = output.error || job.error;
  const displayError =
    formatImageJobError(rawError) || "The image provider could not complete this request.";
  const readyLabel = output.analysis_status === "analyzing"
    ? "Analyzing"
    : output.analysis_status === "pending"
      ? "Analysis queued"
      : output.analysis_status === "failed"
        ? "Analysis failed"
        : "Ready";
  const statusLabel = effectiveStatus === "failed" && failureCount > 1
    ? `${failureCount} failed`
    : effectiveStatus === "ready"
      ? readyLabel
      : outputLabels[effectiveStatus];

  useEffect(() => {
    let cancelled = false;
    setPreviewError(false);
    setPreviewUrl(null);
    if (effectiveStatus !== "ready" || !asset) return;

    const resolvePreview = async () => {
      try {
        const url = await sasTokenService.getBlobUrl(asset.blob_name);
        if (!cancelled) setPreviewUrl(url);
      } catch {
        if (!cancelled) {
          setPreviewUrl(asset.url || null);
          setPreviewError(!asset.url);
        }
      }
    };
    void resolvePreview();
    return () => {
      cancelled = true;
    };
  }, [asset, effectiveStatus]);

  const handleRetry = async () => {
    try {
      await retryJob(job.id);
      toast.success("Added to generation queue");
    } catch (error) {
      toast.error("Could not retry generation", {
        description:
          formatImageJobError(error instanceof Error ? error.message : null) ??
          "Please try again",
      });
    }
  };

  return (
    <Card
      className={cn(
        "group h-full w-full overflow-hidden rounded-xl border-border/70 bg-card p-0 shadow-sm transition-shadow duration-200 hover:shadow-md",
        effectiveStatus === "failed" && "border-destructive/20",
      )}
      aria-label={
        effectiveStatus === "failed" && failureCount > 1
          ? `${failureCount} image outputs failed`
          : `Image ${output.index} of ${job.requested_images}: ${outputLabels[effectiveStatus]}`
      }
    >
      <AspectRatio ratio={aspectRatio} className="relative overflow-hidden bg-muted/30">
        {effectiveStatus === "ready" && previewUrl && !previewError ? (
          <a
            href={previewUrl}
            target="_blank"
            rel="noreferrer"
            className="absolute inset-0 block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset"
            aria-label={`Open generated image ${output.index} in a new tab`}
          >
            <OptimizedImage
              src={previewUrl}
              alt={`${job.prompt}, generated image ${output.index}`}
              fill
              sizes="(max-width: 768px) 100vw, 33vw"
              className="object-cover motion-safe:animate-in motion-safe:fade-in-0"
              onError={() => setPreviewError(true)}
            />
          </a>
        ) : effectiveStatus === "ready" && previewError ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-muted/40 p-5 text-center text-muted-foreground">
            <div className="flex size-10 items-center justify-center rounded-xl border bg-background/70 shadow-xs">
              <ImageOff className="size-5" aria-hidden="true" />
            </div>
            <p className="text-sm font-medium text-foreground">Preview unavailable</p>
            <p className="text-xs">The generated file was saved, but its preview could not be loaded.</p>
          </div>
        ) : effectiveStatus === "ready" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-muted/30 text-muted-foreground">
            <Loader2 className="size-5 motion-safe:animate-spin" aria-hidden="true" />
            <p className="text-xs">Loading preview</p>
          </div>
        ) : effectiveStatus === "failed" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-destructive/[0.06] via-background to-muted/40 p-6 text-center">
            <div className="flex size-10 items-center justify-center rounded-xl border border-destructive/15 bg-background/80 text-destructive shadow-xs">
              <AlertCircle className="size-5" aria-hidden="true" />
            </div>
            <p className="mt-3 text-sm font-medium">
              {failureCount > 1
                ? `${failureCount} images couldn’t be generated`
                : "This image couldn’t be generated"}
            </p>
            <p
              className="mt-1.5 line-clamp-3 max-w-xs text-xs leading-relaxed text-muted-foreground"
              title={rawError ?? undefined}
            >
              {displayError}
            </p>
            {canRetry && (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="mt-4 h-8 shadow-xs"
                onClick={() => void handleRetry()}
                disabled={mutation !== undefined}
                aria-busy={mutation === "retry"}
              >
                {mutation === "retry" ? (
                  <Loader2 className="size-3.5 motion-safe:animate-spin" />
                ) : (
                  <RefreshCw className="size-3.5" />
                )}
                Retry generation
              </Button>
            )}
          </div>
        ) : effectiveStatus === "cancelled" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-muted/30 p-5 text-center text-muted-foreground">
            <div className="flex size-10 items-center justify-center rounded-xl border bg-background/70 shadow-xs">
              <Clock3 className="size-5" aria-hidden="true" />
            </div>
            <p className="text-sm font-medium text-foreground">Generation cancelled</p>
          </div>
        ) : (
          <div className="absolute inset-0 overflow-hidden bg-muted/30">
            <div
              className="absolute inset-0 bg-gradient-to-br from-background/20 via-muted/70 to-background/40 motion-safe:animate-pulse"
              aria-hidden="true"
            />
            <div className="absolute inset-0 flex flex-col items-center justify-center p-5 text-center">
              <div className="flex size-11 items-center justify-center rounded-xl border border-primary/10 bg-background/70 text-primary shadow-sm backdrop-blur-sm">
                <Sparkles className="size-5" aria-hidden="true" />
              </div>
              <p className="mt-3 text-sm font-medium">{outputLabels[effectiveStatus]}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {effectiveStatus === "queued"
                  ? "Waiting for a worker"
                  : `${Math.round(output.progress)}% complete`}
              </p>
            </div>
            {job.status === "submitting" ? (
              <div
                className="absolute inset-x-0 bottom-0 h-1 overflow-hidden bg-primary/10"
                role="progressbar"
                aria-label="Adding image generation to the queue"
              >
                <div className="h-full w-1/3 bg-primary motion-safe:animate-pulse" />
              </div>
            ) : (
              <Progress
                value={output.progress}
                className="absolute inset-x-0 bottom-0 h-1 rounded-none bg-primary/10"
                aria-label={`${outputLabels[effectiveStatus]}: ${Math.round(output.progress)}%`}
              />
            )}
          </div>
        )}

        <div className="pointer-events-none absolute inset-x-2 top-2 flex items-center justify-between gap-2">
          <Badge
            variant="outline"
            className="border-white/10 bg-background/80 text-[10px] shadow-xs backdrop-blur-md"
          >
            {effectiveStatus === "failed" && failureCount > 1
              ? "Batch"
              : `${output.index} / ${job.requested_images}`}
          </Badge>
          <Badge
            variant="outline"
            className={cn(
              "border-white/10 bg-background/80 text-[10px] shadow-xs backdrop-blur-md",
              effectiveStatus === "failed" && "border-destructive/20 text-destructive",
              effectiveStatus === "cancelled" && "text-muted-foreground",
            )}
          >
            {effectiveStatus === "ready" && output.analysis_status === "analyzing" ? (
              <Loader2 className="size-3 motion-safe:animate-spin" aria-hidden="true" />
            ) : effectiveStatus === "ready" && output.analysis_status === "failed" ? (
              <AlertCircle className="size-3 text-amber-500" aria-hidden="true" />
            ) : effectiveStatus === "ready" ? (
              <CheckCircle2 className="size-3 text-emerald-500" aria-hidden="true" />
            ) : null}
            {statusLabel}
          </Badge>
        </div>
      </AspectRatio>

      <div className="space-y-1 border-t border-border/60 px-3 py-2.5">
        <p className="line-clamp-2 text-sm font-medium leading-snug">{job.prompt}</p>
        <p className="text-[11px] text-muted-foreground">
          {job.model} · {job.size.replace("x", " × ")}
        </p>
      </div>
    </Card>
  );
}
