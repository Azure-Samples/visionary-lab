"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CircleStop,
  Clock3,
  ImageOff,
  Layers3,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { OptimizedImage } from "@/components/OptimizedImage";
import { StorylinePlanEditor } from "@/components/storyline/storyline-plan-editor";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { sasTokenService } from "@/services/sas-token";
import type {
  Storyline,
  StorylineFrame,
  StorylineFrameStatus,
  StorylinePlan,
  StorylineStatus,
} from "@/types/storyline";
import {
  buildStorylineImagePrompt,
  isActiveStoryline,
} from "@/types/storyline";
import { cn } from "@/utils/cn";

interface StorylineDetailProps {
  storyline: Storyline;
  isRefreshing?: boolean;
  onRefresh: () => Promise<void>;
  onCancel: () => Promise<void>;
  onStart: () => Promise<void>;
  onRetryPlanning: () => Promise<void>;
  onRetryFrame: (frameId: string) => Promise<void>;
  onRegenerateFrame: (
    frameId: string,
    overrides?: { prompt?: string; copy?: string },
  ) => Promise<void>;
  onSavePlan: (plan: StorylinePlan) => Promise<void>;
}

const statusLabels: Record<StorylineStatus, string> = {
  draft: "Draft",
  planned: "Plan approved",
  queued: "Queued",
  generating: "Generating",
  completed: "Completed",
  partial: "Completed with issues",
  failed: "Failed",
  cancel_requested: "Cancelling",
  cancelled: "Cancelled",
};

const frameStatusLabels: Record<StorylineFrameStatus, string> = {
  pending: "Pending",
  queued: "Queued",
  generating: "Generating",
  saving: "Saving",
  ready: "Ready",
  failed: "Failed",
  cancelled: "Cancelled",
};

function modelLabel(model: string): string {
  if (model === "gpt-image-2") return "GPT-Image-2";
  if (model === "flux-kontext-pro") return "FLUX Kontext Pro";
  return model;
}

function statusBadgeClass(status: StorylineStatus): string {
  if (status === "completed") return "border-emerald-500/30 text-emerald-600";
  if (status === "failed") return "border-destructive/30 text-destructive";
  if (status === "partial") return "border-amber-500/30 text-amber-600";
  return "";
}

function FrameStatusIcon({ status }: { status: StorylineFrameStatus }) {
  if (status === "ready") return <CheckCircle2 className="size-3.5 text-emerald-500" />;
  if (status === "failed") return <AlertCircle className="size-3.5 text-destructive" />;
  if (status === "cancelled") return <CircleStop className="size-3.5" />;
  if (status === "pending" || status === "queued") return <Clock3 className="size-3.5" />;
  return <Loader2 className="size-3.5 motion-safe:animate-spin" />;
}

function StorylineFrameCard({
  frame,
  frameCount,
  isMutating,
  regenerateEnabled,
  onRegenerate,
  onRetry,
}: {
  frame: StorylineFrame;
  frameCount: number;
  isMutating: boolean;
  regenerateEnabled: boolean;
  onRegenerate: () => void;
  onRetry: () => void;
}) {
  const assetBlobName = frame.asset?.blob_name;
  const assetUrl = frame.asset?.url;
  const [previewUrl, setPreviewUrl] = useState<string | null>(
    assetBlobName ? null : (assetUrl ?? null),
  );
  const [previewError, setPreviewError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setPreviewError(false);
    setPreviewUrl(assetBlobName ? null : (assetUrl ?? null));
    if (!assetBlobName) return;
    void sasTokenService
      .getBlobUrl(assetBlobName)
      .then((url) => {
        if (!cancelled) {
          setPreviewError(false);
          setPreviewUrl(url);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPreviewUrl(null);
          setPreviewError(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [assetBlobName, assetUrl]);

  const canRegenerate = regenerateEnabled && frame.status === "ready";
  const canRetry = frame.status === "failed" || frame.status === "cancelled";
  const ratio =
    frame.asset?.width && frame.asset?.height
      ? frame.asset.width / frame.asset.height
      : 1;

  return (
    <Card className="min-w-0 gap-0 overflow-hidden py-0 shadow-sm">
      <AspectRatio ratio={ratio} className="relative bg-muted/30">
        {frame.status === "ready" && previewUrl && !previewError ? (
          <OptimizedImage
            key={previewUrl}
            src={previewUrl}
            alt={`${frame.title || frame.purpose}, frame ${frame.order}`}
            fill
            sizes="(max-width: 768px) 75vw, 260px"
            className="object-cover"
            onError={() => setPreviewError(true)}
          />
        ) : frame.status === "ready" && previewError ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted-foreground">
            <ImageOff className="size-5" />
            <span className="text-xs">Preview unavailable</span>
          </div>
        ) : frame.status === "failed" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-destructive/5 p-4 text-center">
            <AlertCircle className="size-6 text-destructive" />
            <span className="text-sm font-medium">Frame failed</span>
          </div>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted-foreground">
            {frame.status === "generating" || frame.status === "saving" ? (
              <Sparkles className="size-6 text-primary motion-safe:animate-pulse" />
            ) : (
              <Clock3 className="size-6" />
            )}
            <span className="text-xs">{frameStatusLabels[frame.status]}</span>
          </div>
        )}
        <div className="absolute inset-x-2 top-2 flex items-center justify-between gap-2">
          <Badge className="bg-background/85 text-[10px] backdrop-blur" variant="outline">
            {frame.order} / {frameCount}
          </Badge>
          <Badge className="gap-1 bg-background/85 text-[10px] backdrop-blur" variant="outline">
            <FrameStatusIcon status={frame.status} />
            {frameStatusLabels[frame.status]}
          </Badge>
        </div>
      </AspectRatio>
      <CardContent className="space-y-2 border-t p-3">
        <div>
          <h4 className="line-clamp-1 text-sm font-medium">
            {frame.title || `Frame ${frame.order}`}
          </h4>
          <p className="mt-1 line-clamp-2 text-xs font-medium text-foreground/80">
            {frame.purpose}
          </p>
          <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-muted-foreground">
            {frame.prompt}
          </p>
          <p className="mt-2 border-l-2 border-primary/25 pl-2 text-xs leading-relaxed">
            {frame.copy}
          </p>
        </div>
        {frame.error && (
          <p className="line-clamp-2 text-xs text-destructive" title={frame.error}>
            {frame.error}
          </p>
        )}
        <div className="flex items-center justify-between gap-2 pt-1">
          <span className="text-[10px] text-muted-foreground">
            Attempt {frame.attempt + 1}
          </span>
          {canRetry && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onRetry}
              disabled={isMutating}
              aria-label={`Retry ${frame.title || `frame ${frame.order}`}`}
            >
              {isMutating ? (
                <Loader2 className="size-3 motion-safe:animate-spin" />
              ) : (
                <RefreshCw className="size-3" />
              )}
              Retry
            </Button>
          )}
          {canRegenerate && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onRegenerate}
              disabled={isMutating}
              aria-label={`Regenerate ${frame.title || `frame ${frame.order}`}`}
            >
              {isMutating ? (
                <Loader2 className="size-3 motion-safe:animate-spin" />
              ) : (
                <RefreshCw className="size-3" />
              )}
              Regenerate
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function StorylineDetail({
  storyline,
  isRefreshing = false,
  onRefresh,
  onCancel,
  onStart,
  onRetryPlanning,
  onRetryFrame,
  onRegenerateFrame,
  onSavePlan,
}: StorylineDetailProps) {
  const [isCancelling, setIsCancelling] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isRetryingPlanning, setIsRetryingPlanning] = useState(false);
  const [mutatingFrameId, setMutatingFrameId] = useState<string | null>(null);
  const [regenerateFrame, setRegenerateFrame] = useState<StorylineFrame | null>(null);
  const [regeneratePrompt, setRegeneratePrompt] = useState("");
  const [regenerateCopy, setRegenerateCopy] = useState("");
  const [planHasUnsavedChanges, setPlanHasUnsavedChanges] = useState(false);
  const active = isActiveStoryline(storyline.status);
  const canRetryPlanning =
    !storyline.plan &&
    (storyline.status === "draft" ||
      (storyline.status === "failed" && storyline.stage === "planning_failed"));
  const planEditable =
    storyline.settings.review_plan_first &&
    storyline.plan &&
    ["draft", "planned"].includes(storyline.status);
  const frameTotal = useMemo(
    () =>
      storyline.plan?.lanes.reduce(
        (total, lane) => total + lane.frames.length,
        0,
      ) ?? 0,
    [storyline.plan],
  );
  const readyTotal = useMemo(
    () =>
      storyline.plan?.lanes.reduce(
        (total, lane) =>
          total + lane.frames.filter((frame) => frame.status === "ready").length,
        0,
      ) ?? 0,
    [storyline.plan],
  );
  const regeneratePromptTooLong = useMemo(() => {
    if (!regenerateFrame || !storyline.plan) return false;
    return (
      buildStorylineImagePrompt(
        storyline.plan.creative_direction,
        regenerateFrame.purpose,
        regeneratePrompt.trim(),
      ).length > 32000
    );
  }, [regenerateFrame, regeneratePrompt, storyline.plan]);

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      await onCancel();
      toast.success("Storyline cancellation requested");
    } catch (error) {
      toast.error("Could not cancel storyline", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    } finally {
      setIsCancelling(false);
    }
  };

  const handleStart = async () => {
    setIsStarting(true);
    try {
      await onStart();
      toast.success("Storyline generation queued");
    } catch (error) {
      toast.error("Could not start storyline", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    } finally {
      setIsStarting(false);
    }
  };

  const handleRetryPlanning = async () => {
    setIsRetryingPlanning(true);
    try {
      await onRetryPlanning();
      toast.success("Storyline planning restarted");
    } catch (error) {
      toast.error("Could not retry storyline planning", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    } finally {
      setIsRetryingPlanning(false);
    }
  };

  const openRegenerate = (frame: StorylineFrame) => {
    setRegenerateFrame(frame);
    setRegeneratePrompt(frame.prompt);
    setRegenerateCopy(frame.copy);
  };

  const handleRegenerate = async () => {
    if (!regenerateFrame) return;
    setMutatingFrameId(regenerateFrame.frame_id);
    try {
      await onRegenerateFrame(regenerateFrame.frame_id, {
        prompt: regeneratePrompt.trim(),
        copy: regenerateCopy.trim(),
      });
      setRegenerateFrame(null);
      toast.success("Frame queued for regeneration");
    } catch (error) {
      toast.error("Could not regenerate frame", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    } finally {
      setMutatingFrameId(null);
    }
  };

  const handleRetry = async (frameId: string) => {
    setMutatingFrameId(frameId);
    try {
      await onRetryFrame(frameId);
      toast.success("Failed frame queued for retry");
    } catch (error) {
      toast.error("Could not retry frame", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    } finally {
      setMutatingFrameId(null);
    }
  };

  return (
    <div className="space-y-5">
      <Card className="gap-4 border-border/70 shadow-sm">
        <CardHeader className="pb-0">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-xl">{storyline.title}</CardTitle>
                <Badge
                  variant="outline"
                  className={cn("capitalize", statusBadgeClass(storyline.status))}
                >
                  {statusLabels[storyline.status]}
                </Badge>
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
                {storyline.settings.prompt}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => void onRefresh()}
                disabled={isRefreshing}
                aria-label="Refresh storyline"
              >
                <RefreshCw
                  className={cn("size-4", isRefreshing && "motion-safe:animate-spin")}
                />
              </Button>
              {storyline.status === "planned" && (
                <div className="flex flex-col items-end gap-1">
                  <Button
                    type="button"
                    onClick={() => void handleStart()}
                    disabled={isStarting || planHasUnsavedChanges}
                    aria-describedby={
                      planHasUnsavedChanges
                        ? "storyline-unsaved-plan-warning"
                        : undefined
                    }
                  >
                    {isStarting ? (
                      <Loader2 className="size-4 motion-safe:animate-spin" />
                    ) : (
                      <Sparkles className="size-4" />
                    )}
                    Start generation
                  </Button>
                  {planHasUnsavedChanges && (
                    <span
                      id="storyline-unsaved-plan-warning"
                      className="text-[10px] text-amber-600 dark:text-amber-400"
                      role="status"
                    >
                      Save plan changes first
                    </span>
                  )}
                </div>
              )}
              {active && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleCancel()}
                  disabled={isCancelling || storyline.status === "cancel_requested"}
                >
                  {isCancelling ? (
                    <Loader2 className="size-4 motion-safe:animate-spin" />
                  ) : (
                    <CircleStop className="size-4" />
                  )}
                  {storyline.status === "cancel_requested" ? "Cancelling" : "Cancel"}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg border bg-muted/20 p-3">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Frames</p>
              <p className="mt-1 text-sm font-medium">
                {storyline.settings.frame_count} × {storyline.settings.models.length} model
                {storyline.settings.models.length === 1 ? "" : "s"}
              </p>
            </div>
            <div className="rounded-lg border bg-muted/20 p-3">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Channel</p>
              <p className="mt-1 text-sm font-medium capitalize">{storyline.settings.channel}</p>
            </div>
            <div className="rounded-lg border bg-muted/20 p-3">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Copy</p>
              <p className="mt-1 text-sm font-medium capitalize">
                {storyline.settings.copy_depth}
              </p>
            </div>
            <div className="rounded-lg border bg-muted/20 p-3">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Ready</p>
              <p className="mt-1 text-sm font-medium">
                {readyTotal} of {frameTotal || storyline.settings.frame_count * storyline.settings.models.length}
              </p>
            </div>
          </div>

          {(active || storyline.progress > 0) && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span className="capitalize">{storyline.stage.replaceAll("_", " ")}</span>
                <span>{Math.round(storyline.progress)}%</span>
              </div>
              <Progress value={storyline.progress} className="h-1.5" />
            </div>
          )}
        </CardContent>
      </Card>

      {storyline.error && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>Storyline needs attention</AlertTitle>
          <AlertDescription>{storyline.error}</AlertDescription>
        </Alert>
      )}

      {planEditable && (
        <StorylinePlanEditor
          key={`${storyline.id}:${storyline.plan?.version ?? 0}`}
          storyline={storyline}
          onSave={onSavePlan}
          onDirtyChange={setPlanHasUnsavedChanges}
        />
      )}

      {!storyline.plan ? (
        <Card className="border-dashed shadow-none">
          <CardContent className="flex min-h-64 flex-col items-center justify-center p-8 text-center">
            <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Layers3 className="size-6" />
            </div>
            <h3 className="mt-4 font-medium">
              {storyline.settings.review_plan_first
                ? "Waiting for the creative plan"
                : "Preparing model lanes"}
            </h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              {storyline.settings.review_plan_first
                ? "The reviewed plan will appear here with editable, ordered frames. Planning is performed by the backend so source images and creative rules remain consistent."
                : "Ordered frame lanes will appear here as soon as generation is scheduled."}
            </p>
            {canRetryPlanning && (
              <Button
                type="button"
                variant="outline"
                className="mt-5"
                onClick={() => void handleRetryPlanning()}
                disabled={isRetryingPlanning}
              >
                {isRetryingPlanning ? (
                  <Loader2 className="size-4 motion-safe:animate-spin" />
                ) : (
                  <RefreshCw className="size-4" />
                )}
                Retry planning
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <section className="space-y-4" aria-labelledby="storyline-lanes-heading">
          <div className="flex items-center gap-2">
            <Layers3 className="size-4 text-primary" />
            <h2 id="storyline-lanes-heading" className="font-semibold">
              Model comparison lanes
            </h2>
          </div>
          <div className="rounded-lg border bg-muted/20 p-4">
            <p className="text-sm text-muted-foreground">
              {storyline.plan.creative_direction.summary}
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {storyline.plan.creative_direction.palette.map((color) => (
                <Badge key={color} variant="secondary" className="text-[10px]">
                  {color}
                </Badge>
              ))}
            </div>
          </div>
          {storyline.plan.lanes.map((lane) => (
            <div key={lane.lane_id} className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold">
                  {lane.label || modelLabel(lane.model)}
                </h3>
                {lane.reduced_reference_fidelity && (
                  <span className="text-[10px] text-amber-600 dark:text-amber-400">
                    Reduced reference fidelity
                  </span>
                )}
              </div>
              {lane.capability_disclosure && (
                <p className="text-xs text-muted-foreground">
                  {lane.capability_disclosure}
                </p>
              )}
              <div
                className="grid auto-cols-[minmax(15rem,1fr)] grid-flow-col gap-3 overflow-x-auto pb-2"
                aria-label={`${modelLabel(lane.model)} ordered frames`}
              >
                {lane.frames
                  .slice()
                  .sort((a, b) => a.order - b.order)
                  .map((frame) => (
                    <StorylineFrameCard
                      key={frame.frame_id}
                      frame={frame}
                      frameCount={lane.frames.length}
                      isMutating={mutatingFrameId === frame.frame_id}
                      regenerateEnabled={!active}
                      onRegenerate={() => openRegenerate(frame)}
                      onRetry={() => void handleRetry(frame.frame_id)}
                    />
                  ))}
              </div>
            </div>
          ))}
        </section>
      )}

      <Dialog
        open={regenerateFrame !== null}
        onOpenChange={(open) => {
          if (!open && !mutatingFrameId) setRegenerateFrame(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Regenerate {regenerateFrame?.title || `frame ${regenerateFrame?.order ?? ""}`}
            </DialogTitle>
            <DialogDescription>
              Leaving the visual prompt unchanged regenerates only this model lane.
              Changing the visual prompt regenerates the same logical frame across
              every model lane so comparisons stay aligned. Copy stays shared, but
              copy-only edits do not rerender sibling images. For text-only stories,
              changing the first frame also rebuilds its dependent frames.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="regenerate-frame-prompt">Visual prompt</Label>
              <Textarea
                id="regenerate-frame-prompt"
                value={regeneratePrompt}
                onChange={(event) => setRegeneratePrompt(event.target.value)}
                className="min-h-28"
                maxLength={32000}
                aria-describedby={
                  regeneratePromptTooLong
                    ? "regenerate-frame-prompt-error"
                    : undefined
                }
                disabled={mutatingFrameId !== null}
              />
              {regeneratePromptTooLong && (
                <p
                  id="regenerate-frame-prompt-error"
                  className="text-xs text-destructive"
                  role="alert"
                >
                  Shorten this prompt or the shared creative direction to stay within
                  the model’s 32,000-character rendered prompt limit.
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="regenerate-frame-copy">Copy</Label>
              <Textarea
                id="regenerate-frame-copy"
                value={regenerateCopy}
                onChange={(event) => setRegenerateCopy(event.target.value)}
                className="min-h-20"
                maxLength={2000}
                disabled={mutatingFrameId !== null}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setRegenerateFrame(null)}
              disabled={mutatingFrameId !== null}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void handleRegenerate()}
              disabled={
                mutatingFrameId !== null ||
                !regeneratePrompt.trim() ||
                !regenerateCopy.trim() ||
                regeneratePromptTooLong
              }
            >
              {mutatingFrameId ? (
                <Loader2 className="size-4 motion-safe:animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
              Regenerate frame
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
