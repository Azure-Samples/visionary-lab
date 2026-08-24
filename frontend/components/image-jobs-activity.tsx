"use client";

import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  CircleStop,
  ImageIcon,
  Loader2,
  RefreshCw,
  WifiOff,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useImageJobs } from "@/context/image-jobs-context";
import {
  isActiveImageJob,
  isFailedImageJob,
  type ImageJobEntry,
  type ImageJobEntryStatus,
} from "@/types/image-jobs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

const statusLabels: Record<ImageJobEntryStatus, string> = {
  submitting: "Submitting",
  submission_failed: "Submission failed",
  queued: "Queued",
  generating: "Generating",
  saving: "Saving",
  analyzing: "Analyzing",
  completed: "Completed",
  partial: "Completed with issues",
  failed: "Failed",
  cancel_requested: "Cancelling",
  cancelled: "Cancelled",
};

function getStatusText(job: ImageJobEntry): string {
  const rawStage = job.stage?.trim();
  const base = !rawStage || rawStage === job.status
    ? statusLabels[job.status]
    : rawStage.replace(/_/g, " ");
  const ready = job.outputs.filter((output) => output.status === "ready").length;
  const failed = job.outputs.filter((output) => output.status === "failed").length;

  if (job.status === "partial") {
    return `${ready || job.completed_images} ready · ${Math.max(failed, job.failed_images)} failed`;
  }
  if (job.status === "completed") {
    return failed > 0
      ? `${ready} ready · ${failed} failed`
      : `${ready || job.completed_images} of ${job.requested_images} ready`;
  }
  if (isActiveImageJob(job.status) && (ready > 0 || failed > 0)) {
    return `${base} · ${ready} ready${failed > 0 ? ` · ${failed} failed` : ""}`;
  }
  if (failed > 0 || job.failed_images > 0) {
    return `${base} · ${Math.max(failed, job.failed_images)} failed`;
  }
  return base;
}

function JobStatusIcon({ job }: { job: ImageJobEntry }) {
  if (job.status === "completed" && job.failed_images === 0) {
    return <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />;
  }
  if (job.status === "completed" && job.failed_images > 0) {
    return <AlertCircle className="h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />;
  }
  if (job.status === "partial") {
    return <AlertCircle className="h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />;
  }
  if (isFailedImageJob(job.status)) {
    return <XCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />;
  }
  if (job.status === "cancelled") {
    return <CircleStop className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />;
  }
  return <Loader2 className="h-4 w-4 shrink-0 motion-safe:animate-spin text-primary" aria-hidden="true" />;
}

function JobRow({ job, compact = false }: { job: ImageJobEntry; compact?: boolean }) {
  const { cancelJob, retryJob, mutationByJobId } = useImageJobs();
  const mutation = mutationByJobId[job.id];
  const active = isActiveImageJob(job.status);
  const canCancel = active && job.status !== "cancel_requested" && !job.local?.optimistic;
  const canRetry =
    isFailedImageJob(job.status) ||
    job.status === "partial" ||
    job.status === "cancelled";
  const readyAssets = job.outputs.flatMap((output) =>
    output.status === "ready" && output.asset ? [output.asset] : [],
  );

  const handleCancel = async () => {
    try {
      await cancelJob(job.id);
    } catch (error) {
      toast.error("Could not cancel generation", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    }
  };

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
    <article className="rounded-lg border bg-card p-3" aria-label={`Image generation: ${job.prompt}`}>
      <div className="flex items-start gap-2">
        <JobStatusIcon job={job} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className="line-clamp-2 text-sm font-medium leading-tight">{job.prompt}</p>
            <Badge variant="outline" className="shrink-0 text-[10px]">
              {job.requested_images} image{job.requested_images === 1 ? "" : "s"}
            </Badge>
          </div>

          <p className="mt-1 text-xs text-muted-foreground">{getStatusText(job)}</p>

          {active && (
            <div className="mt-2">
              {job.status === "submitting" ? (
                <div
                  className="h-1.5 overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-label="Submitting image generation"
                >
                  <div className="h-full w-1/3 rounded-full bg-primary motion-safe:animate-pulse" />
                </div>
              ) : (
                <Progress
                  value={job.progress}
                  aria-label={`${getStatusText(job)}: ${Math.round(job.progress)}%`}
                />
              )}
            </div>
          )}

          {job.error && (
            <p className="mt-2 line-clamp-3 text-xs text-destructive">{job.error}</p>
          )}

          {!compact && readyAssets.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1" aria-label="Generated image files">
              {readyAssets.slice(0, 4).map((asset) => (
                <Badge key={asset.blob_name} variant="secondary" className="max-w-40 truncate text-[10px]">
                  {asset.blob_name.split("/").pop()}
                </Badge>
              ))}
              {readyAssets.length > 4 && (
                <Badge variant="secondary" className="text-[10px]">
                  +{readyAssets.length - 4}
                </Badge>
              )}
            </div>
          ) : null}

          {canCancel || canRetry ? (
            <div className="mt-2 flex items-center gap-2">
              {canCancel && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => void handleCancel()}
                  disabled={mutation !== undefined}
                  aria-busy={mutation === "cancel"}
                  aria-label={`Cancel generation for ${job.prompt}`}
                >
                  {mutation === "cancel" ? (
                    <Loader2 className="mr-1 h-3 w-3 motion-safe:animate-spin" />
                  ) : (
                    <CircleStop className="mr-1 h-3 w-3" />
                  )}
                  Cancel
                </Button>
              )}
              {canRetry && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => void handleRetry()}
                  disabled={mutation !== undefined}
                  aria-busy={mutation === "retry"}
                  aria-label={`Retry generation for ${job.prompt}`}
                >
                  {mutation === "retry" ? (
                    <Loader2 className="mr-1 h-3 w-3 motion-safe:animate-spin" />
                  ) : (
                    <RefreshCw className="mr-1 h-3 w-3" />
                  )}
                  {job.status === "partial" ? "Retry failed" : "Retry"}
                </Button>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export function ImageJobsButton() {
  const {
    jobs,
    activeCount,
    activeImageCount,
    isHydrating,
    lastError,
    lastSyncedAt,
    connectionState,
  } = useImageJobs();
  const visibleJobs = jobs.slice(0, 20);
  const activityLabel = activeCount > 0
    ? `${activeImageCount} active image${activeImageCount === 1 ? "" : "s"} across ${activeCount} generation${activeCount === 1 ? "" : "s"}`
    : "Image generation activity";
  const announcement = connectionState === "reconnecting"
    ? "Image generation updates are reconnecting"
    : activeCount > 0
      ? activityLabel
      : "No active image generations";

  return (
    <Popover>
      <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </span>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={activityLabel}>
          {isHydrating ? (
            <Loader2 className="h-[1.2rem] w-[1.2rem] motion-safe:animate-spin" />
          ) : connectionState === "reconnecting" ? (
            <WifiOff className="h-[1.2rem] w-[1.2rem] text-amber-500" />
          ) : (
            <ImageIcon className="h-[1.2rem] w-[1.2rem]" />
          )}
          {activeImageCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] text-primary-foreground" aria-hidden="true">
              {activeImageCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(24rem,calc(100vw-1rem))] p-2">
        <div className="flex items-center justify-between gap-2 px-1 py-1">
          <div>
            <h2 className="text-sm font-semibold">Image activity</h2>
            <p className="text-[11px] text-muted-foreground">
              {activeCount > 0
                ? `${activeCount} batch${activeCount === 1 ? "" : "es"} · ${activeImageCount} image${activeImageCount === 1 ? "" : "s"}`
                : lastSyncedAt
                  ? `Synced ${lastSyncedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
                  : "No active generations"}
            </p>
          </div>
          <Button asChild variant="ghost" size="sm" className="h-7 text-xs">
            <Link href="/new-image">Open gallery</Link>
          </Button>
        </div>
        <div className="my-1 h-px bg-border" />
        <div className="max-h-[min(32rem,70vh)] space-y-2 overflow-y-auto p-1">
          {lastError && (
            <div className="flex items-start gap-2 rounded-md bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-300">
              <WifiOff className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <p>Updates are reconnecting. Your generations continue in the background.</p>
            </div>
          )}
          {visibleJobs.length === 0 ? (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              No image generations yet
            </p>
          ) : (
            visibleJobs.map((job) => <JobRow key={job.id} job={job} compact />)
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function ImageJobsInline() {
  const { jobs, activeCount, activeImageCount, connectionState } = useImageJobs();
  const visibleJobs = jobs
    .filter((job, index) => isActiveImageJob(job.status) || index < 2)
    .slice(0, 4);

  if (visibleJobs.length === 0) return null;

  return (
    <section className="mb-6" aria-labelledby="image-activity-heading">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id="image-activity-heading" className="text-sm font-medium">
          Image activity
        </h2>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {connectionState === "reconnecting" && (
            <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
              <WifiOff className="h-3 w-3" aria-hidden="true" />
              Reconnecting
            </span>
          )}
          {activeCount > 0 && (
            <span>
              {activeCount} batch{activeCount === 1 ? "" : "es"} · {activeImageCount} image{activeImageCount === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
        {visibleJobs.map((job) => <JobRow key={job.id} job={job} />)}
      </div>
    </section>
  );
}
