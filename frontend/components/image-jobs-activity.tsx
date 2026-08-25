"use client";

import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  CircleStop,
  Images,
  Loader2,
  RefreshCw,
  Sparkles,
  WifiOff,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useImageJobs } from "@/context/image-jobs-context";
import {
  formatImageJobError,
  isActiveImageJob,
  isFailedImageJob,
  type ImageJobEntry,
  type ImageJobEntryStatus,
} from "@/types/image-jobs";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils/cn";

const statusLabels: Record<ImageJobEntryStatus, string> = {
  submitting: "Adding to queue",
  submission_failed: "Could not queue",
  queued: "Waiting to start",
  generating: "Generating",
  saving: "Saving",
  analyzing: "Analyzing",
  completed: "Completed",
  partial: "Completed with issues",
  failed: "Generation failed",
  cancel_requested: "Cancelling",
  cancelled: "Cancelled",
};

function getStatusText(job: ImageJobEntry): string {
  const base = statusLabels[job.status];
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
  if (isActiveImageJob(job.status) && job.status !== "submitting" && job.progress > 0) {
    return `${base} · ${Math.round(job.progress)}%`;
  }
  if (failed > 1 || job.failed_images > 1) {
    return `${Math.max(failed, job.failed_images)} images failed`;
  }
  return base;
}

function JobStatusIcon({ job }: { job: ImageJobEntry }) {
  if (job.status === "completed" && job.failed_images === 0) {
    return <CheckCircle2 className="size-4 text-emerald-500" aria-hidden="true" />;
  }
  if (job.status === "completed" || job.status === "partial") {
    return <AlertCircle className="size-4 text-amber-500" aria-hidden="true" />;
  }
  if (isFailedImageJob(job.status)) {
    return <XCircle className="size-4 text-destructive" aria-hidden="true" />;
  }
  if (job.status === "cancelled") {
    return <CircleStop className="size-4 text-muted-foreground" aria-hidden="true" />;
  }
  return (
    <Loader2
      className="size-4 text-primary motion-safe:animate-spin"
      aria-hidden="true"
    />
  );
}

function JobRow({ job }: { job: ImageJobEntry }) {
  const { cancelJob, retryJob, mutationByJobId } = useImageJobs();
  const mutation = mutationByJobId[job.id];
  const active = isActiveImageJob(job.status);
  const canCancel = active && job.status !== "cancel_requested" && !job.local?.optimistic;
  const canRetry =
    isFailedImageJob(job.status) ||
    job.status === "partial" ||
    job.status === "cancelled";
  const rawError = job.error;
  const displayError = formatImageJobError(rawError);

  const handleCancel = async () => {
    try {
      await cancelJob(job.id);
    } catch (error) {
      toast.error("Could not cancel generation", {
        description:
          formatImageJobError(error instanceof Error ? error.message : null) ??
          "Please try again",
      });
    }
  };

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
    <article
      className={cn(
        "group flex items-start gap-3 px-3 py-3",
        active && "bg-muted/20",
      )}
      aria-label={`Image generation: ${job.prompt}`}
    >
      <div
        className={cn(
          "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border bg-background/80 shadow-xs",
          active && "border-primary/15 bg-primary/5",
          isFailedImageJob(job.status) && "border-destructive/15 bg-destructive/5",
        )}
      >
        <JobStatusIcon job={job} />
      </div>

      <div className="min-w-0 flex-1">
        <p className="line-clamp-2 text-sm font-medium leading-snug">{job.prompt}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-muted-foreground">
          <span>{getStatusText(job)}</span>
          <span aria-hidden="true">·</span>
          <span>
            {job.requested_images} image{job.requested_images === 1 ? "" : "s"}
          </span>
        </div>

        {active && (
          <div className="mt-2">
            {job.status === "submitting" ? (
              <div
                className="h-1 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-label="Adding image generation to the queue"
              >
                <div className="h-full w-1/3 rounded-full bg-primary motion-safe:animate-pulse" />
              </div>
            ) : (
              <Progress
                value={job.progress}
                className="h-1 bg-muted"
                aria-label={`${getStatusText(job)}: ${Math.round(job.progress)}%`}
              />
            )}
          </div>
        )}

        {displayError && (
          <p
            className="mt-1.5 line-clamp-2 text-[11px] text-destructive/90"
            title={rawError ?? undefined}
          >
            {displayError}
          </p>
        )}
      </div>

      {(canCancel || canRetry) && (
        <div className="flex shrink-0 items-center gap-0.5">
          {canCancel && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7 text-muted-foreground hover:text-foreground"
              onClick={() => void handleCancel()}
              disabled={mutation !== undefined}
              aria-busy={mutation === "cancel"}
              aria-label={`Cancel generation for ${job.prompt}`}
              title="Cancel generation"
            >
              {mutation === "cancel" ? (
                <Loader2 className="size-3.5 motion-safe:animate-spin" />
              ) : (
                <CircleStop className="size-3.5" />
              )}
            </Button>
          )}
          {canRetry && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7 text-muted-foreground hover:text-foreground"
              onClick={() => void handleRetry()}
              disabled={mutation !== undefined}
              aria-busy={mutation === "retry"}
              aria-label={`Retry generation for ${job.prompt}`}
              title={job.status === "partial" ? "Retry failed images" : "Retry generation"}
            >
              {mutation === "retry" ? (
                <Loader2 className="size-3.5 motion-safe:animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
            </Button>
          )}
        </div>
      )}
    </article>
  );
}

function getActiveSummary(activeCount: number, activeImageCount: number): string {
  if (activeCount === 0) return "No active generations";
  if (activeImageCount === 0) {
    return `${activeCount} generation${activeCount === 1 ? "" : "s"} finishing`;
  }
  return `${activeImageCount} image${activeImageCount === 1 ? "" : "s"} remaining across ${activeCount} generation${activeCount === 1 ? "" : "s"}`;
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
  const activeJobs = jobs.filter((job) => isActiveImageJob(job.status));
  const recentJobs = jobs.filter((job) => !isActiveImageJob(job.status)).slice(0, 6);
  const activeSummary = getActiveSummary(activeCount, activeImageCount);
  const activityLabel = activeCount > 0 ? activeSummary : "Image generation activity";
  const announcement = connectionState === "reconnecting"
    ? "Image generation updates are reconnecting"
    : activeSummary;
  const showActivePill = activeCount > 0 && !isHydrating;

  return (
    <Popover>
      <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </span>
      <PopoverTrigger asChild>
        <Button
          variant={showActivePill ? "secondary" : "ghost"}
          size={showActivePill ? "sm" : "icon"}
          className={cn(showActivePill && "rounded-full px-2.5 sm:px-3")}
          aria-label={activityLabel}
        >
          {isHydrating ? (
            <Loader2 className="size-[1.1rem] motion-safe:animate-spin" />
          ) : showActivePill ? (
            <span className="relative flex size-4 items-center justify-center">
              <Sparkles className="size-4" />
              <span
                className={cn(
                  "absolute -right-1 -top-1 size-1.5 rounded-full bg-emerald-500 ring-2 ring-secondary",
                  connectionState === "reconnecting" && "bg-amber-500",
                )}
                aria-hidden="true"
              />
            </span>
          ) : connectionState === "reconnecting" ? (
            <WifiOff className="size-[1.1rem] text-amber-500" />
          ) : (
            <Images className="size-[1.1rem]" />
          )}
          {showActivePill && (
            <>
              <span className="hidden sm:inline">
                {activeImageCount > 0 ? `${activeImageCount} generating` : `${activeCount} finishing`}
              </span>
              <span className="sm:hidden">{activeImageCount || activeCount}</span>
            </>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        className="w-[min(25rem,calc(100vw-1rem))] overflow-hidden rounded-xl border-border/70 p-0 shadow-xl"
      >
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">Generations</h2>
            <p className="truncate text-[11px] text-muted-foreground">
              {activeCount > 0
                ? activeSummary
                : lastSyncedAt
                  ? `Synced ${lastSyncedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
                  : "Your recent image activity"}
            </p>
          </div>
          {connectionState === "reconnecting" && (
            <span className="inline-flex shrink-0 items-center gap-1.5 text-[11px] text-amber-600 dark:text-amber-400">
              <span className="size-1.5 rounded-full bg-amber-500 motion-safe:animate-pulse" />
              Reconnecting
            </span>
          )}
        </div>

        {lastError && (
          <div className="flex items-start gap-2 border-y bg-amber-500/10 px-4 py-2.5 text-xs text-amber-800 dark:text-amber-200">
            <WifiOff className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <p>Updates are reconnecting. Your generations are still running.</p>
          </div>
        )}

        <div className="max-h-[min(34rem,70vh)] overflow-y-auto">
          {activeJobs.length > 0 && (
            <section aria-labelledby="active-generations-heading">
              <h3
                id="active-generations-heading"
                className="px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                In progress
              </h3>
              <div className="divide-y">
                {activeJobs.map((job) => <JobRow key={job.id} job={job} />)}
              </div>
            </section>
          )}

          {recentJobs.length > 0 && (
            <section aria-labelledby="recent-generations-heading">
              <h3
                id="recent-generations-heading"
                className="border-t px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Recent
              </h3>
              <div className="divide-y">
                {recentJobs.map((job) => <JobRow key={job.id} job={job} />)}
              </div>
            </section>
          )}

          {activeJobs.length === 0 && recentJobs.length === 0 && (
            <div className="flex flex-col items-center px-4 py-10 text-center">
              <div className="flex size-10 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                <Images className="size-5" aria-hidden="true" />
              </div>
              <p className="mt-3 text-sm font-medium">No generations yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                New image jobs will keep running here in the background.
              </p>
            </div>
          )}
        </div>

        <div className="border-t bg-muted/20 p-2">
          <Button asChild variant="ghost" size="sm" className="w-full text-xs">
            <Link href="/new-image">Open image gallery</Link>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function ImageJobsInline() {
  const { jobs, activeCount, activeImageCount, connectionState } = useImageJobs();
  const activeJobs = jobs.filter((job) => isActiveImageJob(job.status));
  const supersededJobIds = new Set(
    jobs.flatMap((job) => (job.parent_job_id ? [job.parent_job_id] : [])),
  );
  const latestActionableFailure = jobs.find(
    (job) =>
      !isActiveImageJob(job.status) &&
      !supersededJobIds.has(job.id) &&
      (isFailedImageJob(job.status) || job.status === "partial"),
  );
  const visibleActiveJobs = activeJobs.slice(0, 3);
  const visibleJobs = latestActionableFailure
    ? [...visibleActiveJobs, latestActionableFailure]
    : visibleActiveJobs;
  const hiddenActiveCount = Math.max(0, activeJobs.length - visibleActiveJobs.length);

  if (visibleJobs.length === 0 && connectionState === "connected") return null;

  return (
    <section
      className="mb-6 overflow-hidden rounded-xl border border-border/70 bg-card/80 shadow-sm"
      aria-labelledby="image-activity-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/20 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {activeCount > 0 ? (
              <Sparkles className="size-4" aria-hidden="true" />
            ) : latestActionableFailure ? (
              <AlertCircle className="size-4 text-amber-500" aria-hidden="true" />
            ) : (
              <WifiOff className="size-4 text-amber-500" aria-hidden="true" />
            )}
          </div>
          <div className="min-w-0">
            <h2 id="image-activity-heading" className="text-sm font-medium">
              {activeCount > 0
                ? "Generation queue"
                : latestActionableFailure
                  ? "Generation needs attention"
                  : "Generation updates"}
            </h2>
            <p className="truncate text-[11px] text-muted-foreground">
              {activeCount > 0
                ? getActiveSummary(activeCount, activeImageCount)
                : latestActionableFailure
                  ? "Retry the most recent unsuccessful generation when ready."
                  : "Reconnecting to background updates."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          {connectionState === "reconnecting" && (
            <span className="inline-flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
              <span className="size-1.5 rounded-full bg-amber-500 motion-safe:animate-pulse" />
              Reconnecting
            </span>
          )}
          {hiddenActiveCount > 0 && <span>+{hiddenActiveCount} more active</span>}
        </div>
      </div>

      {visibleJobs.length > 0 && (
        <div className="divide-y">
          {visibleJobs.map((job) => <JobRow key={job.id} job={job} />)}
        </div>
      )}
    </section>
  );
}
