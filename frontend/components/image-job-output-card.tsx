"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
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
  isFailedImageJob,
  type ImageJobEntry,
  type ImageJobOutput,
  type ImageOutputStatus,
} from "@/types/image-jobs";

interface ImageJobOutputCardProps {
  job: ImageJobEntry;
  output: ImageJobOutput;
}

const outputLabels: Record<ImageOutputStatus, string> = {
  queued: "Reserved",
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
  const readyLabel = output.analysis_status === "analyzing"
    ? "Analyzing"
    : output.analysis_status === "pending"
      ? "Analysis queued"
      : output.analysis_status === "failed"
        ? "Analysis failed"
        : "Ready";

  useEffect(() => {
    let cancelled = false;
    setPreviewError(false);
    setPreviewUrl(null);
    if (effectiveStatus !== "ready" || !asset) return;

    const resolvePreview = async () => {
      try {
        const url = await sasTokenService.getBlobUrl(asset.blob_name, false);
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
      toast.success("Generation queued again");
    } catch (error) {
      toast.error("Could not retry generation", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    }
  };

  return (
    <Card
      className="group h-full w-full overflow-hidden rounded-xl border border-dashed bg-card p-0"
      aria-label={`Image ${output.index} of ${job.requested_images}: ${outputLabels[effectiveStatus]}`}
    >
      <AspectRatio ratio={aspectRatio} className="relative overflow-hidden bg-muted/60">
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
        ) : effectiveStatus === "failed" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-destructive/5 p-5 text-center text-destructive">
            <AlertCircle className="h-8 w-8" aria-hidden="true" />
            <p className="line-clamp-3 text-xs">
              {output.error || job.error || "This image could not be generated."}
            </p>
            {canRetry && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8"
                onClick={() => void handleRetry()}
                disabled={mutation !== undefined}
                aria-busy={mutation === "retry"}
              >
                {mutation === "retry" ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 motion-safe:animate-spin" />
                ) : (
                  <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                )}
                {job.status === "partial" ? "Retry failed" : "Retry batch"}
              </Button>
            )}
          </div>
        ) : effectiveStatus === "cancelled" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-5 text-center text-muted-foreground">
            <Clock3 className="h-8 w-8" aria-hidden="true" />
            <p className="text-xs">Generation cancelled</p>
          </div>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-5 text-center">
            <div className="relative flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
              <span className="absolute inset-0 rounded-full border border-primary/20 motion-safe:animate-ping" aria-hidden="true" />
            </div>
            <div className="w-full max-w-40 space-y-2">
              <p className="text-xs font-medium">{outputLabels[effectiveStatus]}</p>
              {job.status === "submitting" ? (
                <div className="h-1.5 overflow-hidden rounded-full bg-primary/10">
                  <div className="h-full w-1/3 rounded-full bg-primary motion-safe:animate-pulse" />
                </div>
              ) : (
                <Progress
                  value={output.progress}
                  aria-label={`${outputLabels[effectiveStatus]}: ${Math.round(output.progress)}%`}
                />
              )}
            </div>
          </div>
        )}

        <div className="pointer-events-none absolute inset-x-2 top-2 flex items-center justify-between gap-2">
          <Badge variant="secondary" className="bg-background/85 text-[10px] backdrop-blur">
            {output.index} / {job.requested_images}
          </Badge>
          <Badge
            variant={effectiveStatus === "failed" ? "destructive" : "secondary"}
            className="bg-background/85 text-[10px] text-foreground backdrop-blur"
          >
            {effectiveStatus === "ready" && output.analysis_status === "analyzing" ? (
              <Loader2 className="mr-1 h-3 w-3 motion-safe:animate-spin" aria-hidden="true" />
            ) : effectiveStatus === "ready" && output.analysis_status === "failed" ? (
              <AlertCircle className="mr-1 h-3 w-3 text-amber-500" aria-hidden="true" />
            ) : effectiveStatus === "ready" ? (
              <CheckCircle2 className="mr-1 h-3 w-3 text-emerald-500" aria-hidden="true" />
            ) : null}
            {effectiveStatus === "ready" ? readyLabel : outputLabels[effectiveStatus]}
          </Badge>
        </div>
      </AspectRatio>

      <div className="space-y-1 p-3">
        <p className="line-clamp-2 text-sm font-medium leading-snug">{job.prompt}</p>
        <p className="text-xs text-muted-foreground">
          {job.model} · {job.size.replace("x", " × ")}
        </p>
      </div>
    </Card>
  );
}
