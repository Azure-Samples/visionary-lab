"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Loader2,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  Storyline,
  StorylineFrame,
  StorylinePlan,
} from "@/types/storyline";
import { buildStorylineImagePrompt } from "@/types/storyline";

interface StorylinePlanEditorProps {
  storyline: Storyline;
  onSave: (plan: StorylinePlan) => Promise<void>;
  onDirtyChange?: (isDirty: boolean) => void;
}

function createId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function reindexFrames(frames: StorylineFrame[]): StorylineFrame[] {
  return frames.map((frame, index) => ({ ...frame, order: index + 1 }));
}

function modelLabel(model: string): string {
  if (model === "gpt-image-2") return "GPT-Image-2";
  if (model === "flux-kontext-pro") return "FLUX Kontext Pro";
  return model;
}

export function StorylinePlanEditor({
  storyline,
  onSave,
  onDirtyChange,
}: StorylinePlanEditorProps) {
  const [draft, setDraft] = useState<StorylinePlan | null>(storyline.plan ?? null);
  const [isSaving, setIsSaving] = useState(false);
  const isDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(storyline.plan),
    [draft, storyline.plan],
  );

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  if (!draft) return null;

  const firstLane = draft.lanes[0];
  const frameCount = firstLane?.frames.length ?? 0;

  const updateLogicalFrame = (
    planFrameId: string,
    field: "title" | "purpose" | "prompt" | "copy",
    value: string,
  ) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            lanes: current.lanes.map((lane) => ({
              ...lane,
              frames: lane.frames.map((frame) =>
                frame.plan_frame_id === planFrameId
                  ? { ...frame, [field]: value }
                  : frame,
              ),
            })),
          }
        : current,
    );
  };

  const moveLogicalFrame = (fromIndex: number, direction: -1 | 1) => {
    const toIndex = fromIndex + direction;
    if (toIndex < 0 || toIndex >= frameCount) return;
    setDraft((current) =>
      current
        ? {
            ...current,
            lanes: current.lanes.map((lane) => {
              const frames = [...lane.frames];
              [frames[fromIndex], frames[toIndex]] = [frames[toIndex], frames[fromIndex]];
              return { ...lane, frames: reindexFrames(frames) };
            }),
          }
        : current,
    );
  };

  const removeLogicalFrame = (planFrameId: string) => {
    if (frameCount <= 2) {
      toast.warning("A storyline needs at least two frames");
      return;
    }
    setDraft((current) =>
      current
        ? {
            ...current,
            lanes: current.lanes.map((lane) => ({
              ...lane,
              frames: reindexFrames(
                lane.frames.filter((frame) => frame.plan_frame_id !== planFrameId),
              ),
            })),
          }
        : current,
    );
  };

  const addLogicalFrame = () => {
    if (frameCount >= 10) {
      toast.warning("A storyline can contain up to 10 frames");
      return;
    }
    const planFrameId = createId("plan-frame");
    setDraft((current) =>
      current
        ? {
            ...current,
            lanes: current.lanes.map((lane) => ({
              ...lane,
              frames: [
                ...lane.frames,
                {
                  frame_id: createId("frame"),
                  plan_frame_id: planFrameId,
                  lane_id: lane.lane_id,
                  order: lane.frames.length + 1,
                  title: "New frame",
                  purpose: "Continue the campaign narrative",
                  prompt: storyline.settings.prompt,
                  copy: "Add campaign copy",
                  status: "pending",
                  attempt: 0,
                  asset: null,
                  image_job_id: null,
                  error: null,
                },
              ],
            })),
          }
        : current,
    );
  };

  const handleSave = async () => {
    if (!isDirty) return;
    const hasMissingContent = draft.lanes.some((lane) =>
      lane.frames.some(
        (frame) =>
          !frame.purpose.trim() || !frame.prompt.trim() || !frame.copy.trim(),
      ),
    );
    const direction = draft.creative_direction;
    if (
      !direction.summary.trim() ||
      !direction.visual_style.trim() ||
      !direction.tone.trim() ||
      direction.palette.length === 0 ||
      direction.continuity_rules.length === 0 ||
      hasMissingContent
    ) {
      toast.error("Complete the creative direction and every frame before saving");
      return;
    }
    if (direction.palette.length > 8) {
      toast.error("Use no more than eight palette entries");
      return;
    }
    if (direction.continuity_rules.length > 12) {
      toast.error("Use no more than twelve continuity rules");
      return;
    }
    const hasOversizedRenderedPrompt = draft.lanes[0]?.frames.some(
      (frame) =>
        buildStorylineImagePrompt(
          direction,
          frame.purpose.trim(),
          frame.prompt.trim(),
        ).length > 32000,
    );
    if (hasOversizedRenderedPrompt) {
      toast.error(
        "Shorten the creative direction or visual prompts so every rendered image prompt stays within 32,000 characters",
      );
      return;
    }
    setIsSaving(true);
    try {
      await onSave({
        ...draft,
        version: Math.max(storyline.plan?.version ?? 0, draft.version) + 1,
        creative_direction: {
          ...direction,
          summary: direction.summary.trim(),
          visual_style: direction.visual_style.trim(),
          tone: direction.tone.trim(),
        },
        lanes: draft.lanes.map((lane) => ({
          ...lane,
          frames: reindexFrames(lane.frames).map((frame) => ({
            ...frame,
            title: frame.title?.trim() || null,
            purpose: frame.purpose.trim(),
            prompt: frame.prompt.trim(),
            copy: frame.copy.trim(),
          })),
        })),
      });
      toast.success("Storyline plan saved");
    } catch (error) {
      toast.error("Could not save the plan", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="border-primary/20 bg-primary/[0.02] shadow-sm">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Review creative plan</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              Changes apply atomically across the model comparison lanes.
            </p>
          </div>
          <Button
            onClick={() => void handleSave()}
            disabled={isSaving || !isDirty}
            size="sm"
          >
            {isSaving ? (
              <Loader2 className="size-3.5 motion-safe:animate-spin" />
            ) : (
              <Save className="size-3.5" />
            )}
            Save plan
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="storyline-plan-summary">Direction summary</Label>
            <Textarea
              id="storyline-plan-summary"
              value={draft.creative_direction.summary}
              onChange={(event) =>
                setDraft((current) =>
                  current
                    ? {
                        ...current,
                        creative_direction: {
                          ...current.creative_direction,
                          summary: event.target.value,
                        },
                      }
                    : current,
                )
              }
              placeholder="What this sequence communicates"
              className="min-h-24"
              maxLength={2000}
              disabled={isSaving}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="storyline-visual-style">Visual style</Label>
            <Textarea
              id="storyline-visual-style"
              value={draft.creative_direction.visual_style}
              onChange={(event) =>
                setDraft((current) =>
                  current
                    ? {
                        ...current,
                        creative_direction: {
                          ...current.creative_direction,
                          visual_style: event.target.value,
                        },
                      }
                    : current,
                )
              }
              placeholder="Shared palette, lighting, lens, composition, subjects, and continuity rules"
              className="min-h-24"
              maxLength={1000}
              required
              disabled={isSaving}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="storyline-tone">Tone</Label>
            <Input
              id="storyline-tone"
              value={draft.creative_direction.tone}
              onChange={(event) =>
                setDraft((current) =>
                  current
                    ? {
                        ...current,
                        creative_direction: {
                          ...current.creative_direction,
                          tone: event.target.value,
                        },
                      }
                    : current,
                )
              }
              maxLength={500}
              required
              disabled={isSaving}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="storyline-palette">Palette</Label>
            <Input
              id="storyline-palette"
              value={draft.creative_direction.palette.join(", ")}
              onChange={(event) =>
                setDraft((current) =>
                  current
                    ? {
                        ...current,
                        creative_direction: {
                          ...current.creative_direction,
                          palette: event.target.value
                            .split(",")
                            .map((item) => item.trim())
                            .filter(Boolean),
                        },
                      }
                    : current,
                )
              }
              placeholder="Cobalt, warm white, coral accent"
              required
              disabled={isSaving}
            />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="storyline-continuity">Continuity rules</Label>
            <Textarea
              id="storyline-continuity"
              value={draft.creative_direction.continuity_rules.join("\n")}
              onChange={(event) =>
                setDraft((current) =>
                  current
                    ? {
                        ...current,
                        creative_direction: {
                          ...current.creative_direction,
                          continuity_rules: event.target.value
                            .split("\n")
                            .map((item) => item.trim())
                            .filter(Boolean),
                        },
                      }
                    : current,
                )
              }
              placeholder="One rule per line"
              className="min-h-24"
              required
              disabled={isSaving}
            />
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">Logical frames</h3>
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
              {frameCount} frames shared by
            </span>
            {draft.lanes.map((lane) => (
              <span
                key={lane.lane_id}
                className="rounded-full border px-2 py-0.5 text-[10px] text-muted-foreground"
              >
                {lane.label || modelLabel(lane.model)}
              </span>
            ))}
          </div>
          <div className="space-y-2">
            {firstLane?.frames.map((frame, index) => (
                  <div
                    key={frame.frame_id}
                    className="grid gap-3 rounded-lg border bg-background p-3 md:grid-cols-[auto_minmax(10rem,0.45fr)_minmax(12rem,0.75fr)_minmax(16rem,1.3fr)]"
                  >
                    <div className="flex items-start gap-1">
                      <span className="flex size-7 items-center justify-center rounded-md bg-muted text-xs font-semibold">
                        {index + 1}
                      </span>
                      <div className="flex flex-col">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            onClick={() => moveLogicalFrame(index, -1)}
                            disabled={index === 0 || isSaving}
                            aria-label={`Move frame ${index + 1} earlier`}
                          >
                            <ArrowUp className="size-3.5" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            onClick={() => moveLogicalFrame(index, 1)}
                            disabled={index === frameCount - 1 || isSaving}
                            aria-label={`Move frame ${index + 1} later`}
                          >
                            <ArrowDown className="size-3.5" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="size-7 text-destructive hover:text-destructive"
                            onClick={() => removeLogicalFrame(frame.plan_frame_id)}
                            disabled={frameCount <= 2 || isSaving}
                            aria-label={`Remove frame ${index + 1}`}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor={`frame-title-${frame.frame_id}`}>Title</Label>
                      <Input
                        id={`frame-title-${frame.frame_id}`}
                        value={frame.title ?? ""}
                        onChange={(event) =>
                          updateLogicalFrame(
                            frame.plan_frame_id,
                            "title",
                            event.target.value,
                          )
                        }
                        maxLength={256}
                        disabled={isSaving}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor={`frame-purpose-${frame.frame_id}`}>Purpose</Label>
                      <Textarea
                        id={`frame-purpose-${frame.frame_id}`}
                        value={frame.purpose}
                        onChange={(event) =>
                          updateLogicalFrame(
                            frame.plan_frame_id,
                            "purpose",
                            event.target.value,
                          )
                        }
                        className="min-h-20 resize-y"
                        maxLength={1000}
                        required
                        disabled={isSaving}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor={`frame-prompt-${frame.frame_id}`}>Visual prompt</Label>
                      <Textarea
                        id={`frame-prompt-${frame.frame_id}`}
                        value={frame.prompt}
                        onChange={(event) =>
                          updateLogicalFrame(
                            frame.plan_frame_id,
                            "prompt",
                            event.target.value,
                          )
                        }
                        className="min-h-20 resize-y"
                        maxLength={32000}
                        required
                        disabled={isSaving}
                      />
                    </div>
                    <div className="space-y-1.5 md:col-start-3 md:col-span-2">
                      <Label htmlFor={`frame-copy-${frame.frame_id}`}>Copy</Label>
                      <Textarea
                        id={`frame-copy-${frame.frame_id}`}
                        value={frame.copy}
                        onChange={(event) =>
                          updateLogicalFrame(
                            frame.plan_frame_id,
                            "copy",
                            event.target.value,
                          )
                        }
                        className="min-h-16 resize-y"
                        maxLength={2000}
                        required
                        disabled={isSaving}
                      />
                    </div>
                  </div>
            ))}
          </div>
        </div>

        <Button
          type="button"
          variant="outline"
          className="w-full border-dashed"
          onClick={addLogicalFrame}
          disabled={frameCount >= 10 || isSaving}
        >
          <Plus className="size-4" />
          Add frame to every lane
        </Button>
      </CardContent>
    </Card>
  );
}
