"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Images,
  Loader2,
  Plus,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  createStoryline,
  getStorylineCapabilities,
  uploadStorylineReferences,
} from "@/services/storylines";
import type {
  Storyline,
  StorylineChannel,
  StorylineCopyDepth,
  StorylineCreateRequest,
  StorylineModel,
  StorylineModelCapability,
} from "@/types/storyline";
import { cn } from "@/utils/cn";

interface StorylineComposerProps {
  onCreated: (storyline: Storyline) => void;
}

const channelOptions: Array<{ value: StorylineChannel; label: string }> = [
  { value: "instagram", label: "Instagram" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "tiktok", label: "TikTok" },
  { value: "facebook", label: "Facebook" },
  { value: "x", label: "X" },
  { value: "web", label: "Web campaign" },
];

function createRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `storyline-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function ReferenceUploads({
  files,
  onChange,
  disabled,
}: {
  files: File[];
  onChange: (files: File[]) => void;
  disabled: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const previewUrls = useMemo(
    () => files.map((file) => URL.createObjectURL(file)),
    [files],
  );

  useEffect(
    () => () => previewUrls.forEach((url) => URL.revokeObjectURL(url)),
    [previewUrls],
  );

  const addFiles = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    const valid = selected.filter((file) => {
      if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
        toast.error(`${file.name} is not a supported image`);
        return false;
      }
      if (file.size >= 50 * 1024 * 1024) {
        toast.error(`${file.name} must be smaller than 50 MB`);
        return false;
      }
      return true;
    });
    const additions = valid.slice(0, Math.max(0, 10 - files.length));
    if (valid.length > additions.length) {
      toast.warning("A storyline can use up to 10 reference images");
    }
    onChange([...files, ...additions]);
    event.target.value = "";
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <Label htmlFor="storyline-references">Reference images</Label>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Optional visual anchors for subjects, products, palette, or art direction.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={disabled || files.length >= 10}
        >
          <Plus className="size-3.5" />
          Add images
        </Button>
      </div>
      <input
        id="storyline-references"
        ref={inputRef}
        type="file"
        className="sr-only"
        accept="image/jpeg,image/png,image/webp"
        multiple
        onChange={addFiles}
        disabled={disabled}
      />
      {files.length > 0 ? (
        <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Selected references">
          {files.map((file, index) => (
            <div
              key={`${file.name}:${file.lastModified}:${index}`}
              className="relative shrink-0"
            >
              <div className="relative size-16 overflow-hidden rounded-lg border bg-muted">
                <Image
                  src={previewUrls[index]}
                  alt={`${file.name}, reference ${index + 1}`}
                  fill
                  sizes="64px"
                  className="object-cover"
                  unoptimized
                />
              </div>
              <span className="absolute bottom-1 left-1 rounded bg-black/65 px-1 text-[10px] text-white">
                {index + 1}
              </span>
              <Button
                type="button"
                variant="secondary"
                size="icon"
                className="absolute -right-2 -top-2 size-6 rounded-full shadow-sm"
                aria-label={`Remove ${file.name}`}
                onClick={() => onChange(files.filter((_, itemIndex) => itemIndex !== index))}
                disabled={disabled}
              >
                <X className="size-3" />
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <button
          type="button"
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed p-4 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:bg-muted/30 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
        >
          <Images className="size-4" />
          Start from text, or add one or more references
        </button>
      )}
    </div>
  );
}

export function StorylineComposer({ onCreated }: StorylineComposerProps) {
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [frameCount, setFrameCount] = useState("4");
  const [models, setModels] = useState<StorylineModel[]>([]);
  const [capabilities, setCapabilities] = useState<StorylineModelCapability[]>([]);
  const [isLoadingCapabilities, setIsLoadingCapabilities] = useState(true);
  const [capabilitiesError, setCapabilitiesError] = useState<string | null>(null);
  const [channel, setChannel] = useState<StorylineChannel>("instagram");
  const [size, setSize] = useState("1024x1536");
  const [copyDepth, setCopyDepth] = useState<StorylineCopyDepth>("balanced");
  const [reviewPlanFirst, setReviewPlanFirst] = useState(false);
  const [referenceFiles, setReferenceFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionStage, setSubmissionStage] = useState<string | null>(null);
  const reducedFidelityModels = capabilities.filter(
    (capability) =>
      models.includes(capability.model) &&
      referenceFiles.length > capability.max_reference_images,
  );
  const sizeOptions = useMemo(() => {
    const selectedCapabilities = capabilities.filter((capability) =>
      models.includes(capability.model),
    );
    if (selectedCapabilities.length === 0) return ["1024x1024"];
    return selectedCapabilities
      .slice(1)
      .reduce(
        (intersection, capability) =>
          intersection.filter((option) =>
            capability.recommended_sizes.includes(option),
          ),
        [...selectedCapabilities[0].recommended_sizes],
      )
      .filter((option, index, options) => options.indexOf(option) === index);
  }, [capabilities, models]);
  const hasCommonSize = models.length > 0 && sizeOptions.length > 0;

  useEffect(() => {
    let cancelled = false;
    void getStorylineCapabilities()
      .then((available) => {
        if (cancelled) return;
        setCapabilities(available);
        setCapabilitiesError(null);
        setModels((current) => {
          const supported = current.filter((model) =>
            available.some((capability) => capability.model === model),
          );
          return supported.length > 0
            ? supported
            : available.length > 0
              ? [available[0].model]
              : [];
        });
      })
      .catch((error) => {
        if (cancelled) return;
        setCapabilities([]);
        setModels([]);
        setCapabilitiesError(
          error instanceof Error
            ? error.message
            : "Could not load configured image models",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoadingCapabilities(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (sizeOptions.length > 0 && !sizeOptions.includes(size)) {
      setSize(sizeOptions.includes("1024x1024") ? "1024x1024" : sizeOptions[0]);
    }
  }, [size, sizeOptions]);

  const toggleModel = (model: StorylineModel, checked: boolean) => {
    if (checked) {
      setModels((current) => Array.from(new Set([...current, model])));
      return;
    }
    setModels((current) => {
      if (current.length === 1) {
        toast.warning("Select at least one image model");
        return current;
      }
      return current.filter((item) => item !== model);
    });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (
      !title.trim() ||
      (!brief.trim() && referenceFiles.length === 0) ||
      models.length === 0
    ) {
      return;
    }
    setIsSubmitting(true);
    try {
      const requestId = createRequestId();
      let references: StorylineCreateRequest["references"] = undefined;
      if (referenceFiles.length > 0) {
        setSubmissionStage("Uploading durable references…");
        references = await uploadStorylineReferences(referenceFiles);
      }
      setSubmissionStage("Creating storyline…");
      const request: StorylineCreateRequest = {
        title: title.trim(),
        settings: {
          prompt: brief.trim(),
          frame_count: Number(frameCount),
          models,
          channel,
          copy_depth: copyDepth,
          size,
          quality: "high",
          background: "auto",
          output_format: "png",
          output_compression: 100,
          input_fidelity: "high",
          review_plan_first: reviewPlanFirst,
          folder_path: null,
          analysis_enabled: false,
        },
        references,
        idempotency_key: requestId,
        client_request_id: requestId,
      };
      const storyline = await createStoryline(request);
      onCreated(storyline);
      toast.success(
        reviewPlanFirst ? "Storyline draft created" : "Storyline created",
        {
          description: reviewPlanFirst
            ? "Its creative plan will appear for review before generation."
            : "Generation progress will appear in the storyline workspace.",
        },
      );
      setTitle("");
      setBrief("");
      setReferenceFiles([]);
    } catch (error) {
      toast.error("Could not create storyline", {
        description: error instanceof Error ? error.message : "Please try again",
      });
    } finally {
      setSubmissionStage(null);
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="pb-4">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="size-4" />
          </div>
          <div>
            <CardTitle className="text-base">New storyline</CardTitle>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Build an ordered campaign from a shared creative direction.
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form className="space-y-5" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="storyline-title">Name</Label>
            <Input
              id="storyline-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Summer launch campaign"
              maxLength={256}
              required
              disabled={isSubmitting}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="storyline-brief">Creative brief</Label>
            <Textarea
              id="storyline-brief"
              value={brief}
              onChange={(event) => setBrief(event.target.value)}
              placeholder="Describe the audience, story arc, subjects, visual language, and outcome…"
              className="min-h-28 resize-y"
              maxLength={32000}
              aria-describedby="storyline-brief-help"
              disabled={isSubmitting}
            />
            <p id="storyline-brief-help" className="text-xs text-muted-foreground">
              Optional when reference images provide the starting point.
            </p>
          </div>

          <ReferenceUploads
            files={referenceFiles}
            onChange={setReferenceFiles}
            disabled={isSubmitting}
          />

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Compare models</legend>
            {isLoadingCapabilities && (
              <div className="flex items-center gap-2 rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 motion-safe:animate-spin" />
                Loading configured image models…
              </div>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {capabilities.map((capability) => {
                const model = capability.model;
                const checked = models.includes(model);
                return (
                  <label
                    key={model}
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors",
                      checked && "border-primary/50 bg-primary/5",
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) => toggleModel(model, value === true)}
                      disabled={isSubmitting}
                      aria-label={`Use ${capability.display_name}`}
                    />
                    <span>
                      <span className="block text-sm font-medium">
                        {capability.display_name}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {capability.disclosure}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          {!isLoadingCapabilities && capabilities.length === 0 && (
            <Alert variant="destructive">
              <AlertTriangle />
              <AlertTitle>
                {capabilitiesError
                  ? "Could not load image-model capabilities"
                  : "No storyline model is configured"}
              </AlertTitle>
              <AlertDescription>
                {capabilitiesError ??
                  "Configure at least one image model before creating a storyline."}
              </AlertDescription>
            </Alert>
          )}

          {reducedFidelityModels.length > 0 && (
            <Alert className="border-amber-500/30 bg-amber-500/5">
              <AlertTriangle className="text-amber-600" />
              <AlertTitle>Reduced-fidelity comparison lane</AlertTitle>
              <AlertDescription>
                {reducedFidelityModels.map((capability) => capability.display_name).join(", ")}
                {" "}accepts one reference image per render. Those lanes may drift more
                in faces, products, typography, and fine identity details.
              </AlertDescription>
            </Alert>
          )}

          {models.length > 0 && !hasCommonSize && (
            <Alert variant="destructive">
              <AlertTriangle />
              <AlertTitle>No common image size</AlertTitle>
              <AlertDescription>
                The selected model lanes do not share a recommended size. Choose a
                different model combination before generating the comparison.
              </AlertDescription>
            </Alert>
          )}

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="storyline-frame-count">Frames</Label>
              <Select
                value={frameCount}
                onValueChange={setFrameCount}
                disabled={isSubmitting}
              >
                <SelectTrigger id="storyline-frame-count">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Array.from({ length: 9 }, (_, index) => index + 2).map((count) => (
                    <SelectItem key={count} value={String(count)}>
                      {count} frames
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="storyline-channel">Channel</Label>
              <Select
                value={channel}
                onValueChange={(value) => {
                  const nextChannel = value as StorylineChannel;
                  setChannel(nextChannel);
                  const suggested = ["instagram", "tiktok"].includes(nextChannel)
                    ? "1024x1536"
                    : "1536x1024";
                  if (sizeOptions.includes(suggested)) setSize(suggested);
                }}
                disabled={isSubmitting}
              >
                <SelectTrigger id="storyline-channel">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {channelOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="storyline-size">Size</Label>
              <Select value={size} onValueChange={setSize} disabled={isSubmitting}>
                <SelectTrigger id="storyline-size">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {sizeOptions.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option === "auto" ? "Auto" : option.replace("x", " × ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-[10px] text-muted-foreground">
                Suggested by channel; you can override it.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <Label id="storyline-copy-depth-label">Copy depth</Label>
            <ToggleGroup
              type="single"
              value={copyDepth}
              onValueChange={(value) => {
                if (value) setCopyDepth(value as StorylineCopyDepth);
              }}
              aria-labelledby="storyline-copy-depth-label"
              className="grid grid-cols-3"
              disabled={isSubmitting}
            >
              <ToggleGroupItem value="punchy">Punchy</ToggleGroupItem>
              <ToggleGroupItem value="balanced">Balanced</ToggleGroupItem>
              <ToggleGroupItem value="detailed">Detailed</ToggleGroupItem>
            </ToggleGroup>
          </div>

          <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3">
            <Checkbox
              checked={reviewPlanFirst}
              onCheckedChange={(value) => setReviewPlanFirst(value === true)}
              disabled={isSubmitting}
              aria-label="Review creative plan before generation"
            />
            <span>
              <span className="block text-sm font-medium">Review plan first</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                Edit, reorder, add, or remove frames before image generation starts.
              </span>
            </span>
          </label>

          <Button
            type="submit"
            className="w-full"
            disabled={
              isSubmitting ||
              isLoadingCapabilities ||
              !title.trim() ||
              (!brief.trim() && referenceFiles.length === 0) ||
              models.length === 0 ||
              !hasCommonSize
            }
          >
            {isSubmitting ? (
              <Loader2 className="size-4 motion-safe:animate-spin" />
            ) : (
              <Sparkles className="size-4" />
            )}
            {submissionStage ??
              (reviewPlanFirst ? "Create and review plan" : "Generate storyline")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
