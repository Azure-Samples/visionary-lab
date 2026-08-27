export const STORYLINE_MODELS = [
  "gpt-image-2",
  "flux-kontext-pro",
] as const;

export type StorylineModel = string;

export const STORYLINE_CHANNELS = [
  "instagram",
  "linkedin",
  "tiktok",
  "facebook",
  "x",
  "web",
] as const;

export type StorylineChannel = (typeof STORYLINE_CHANNELS)[number];

export const STORYLINE_COPY_DEPTHS = [
  "punchy",
  "balanced",
  "detailed",
] as const;

export type StorylineCopyDepth = (typeof STORYLINE_COPY_DEPTHS)[number];

export const STORYLINE_STATUSES = [
  "draft",
  "planned",
  "queued",
  "generating",
  "completed",
  "partial",
  "failed",
  "cancel_requested",
  "cancelled",
] as const;

export type StorylineStatus = (typeof STORYLINE_STATUSES)[number];

export const STORYLINE_FRAME_STATUSES = [
  "pending",
  "queued",
  "generating",
  "saving",
  "ready",
  "failed",
  "cancelled",
] as const;

export type StorylineFrameStatus = (typeof STORYLINE_FRAME_STATUSES)[number];

export interface StorylineReference {
  reference_id: string;
  blob_name: string;
  url: string;
  container: string;
  content_type: string;
  original_filename: string;
  order: number;
}

export interface StorylineSettings {
  prompt: string;
  frame_count: number;
  models: StorylineModel[];
  channel: StorylineChannel | string;
  copy_depth: StorylineCopyDepth;
  size: string;
  quality: string;
  background: string;
  output_format: string;
  output_compression: number;
  input_fidelity: "low" | "high";
  review_plan_first: boolean;
  folder_path?: string | null;
  analysis_enabled: boolean;
}

export interface StorylineFrameAsset {
  blob_name: string;
  url: string;
  container?: string | null;
  content_type?: string | null;
  width?: number | null;
  height?: number | null;
  [key: string]: unknown;
}

export interface StorylineFrame {
  frame_id: string;
  plan_frame_id: string;
  lane_id: string;
  order: number;
  title?: string | null;
  purpose: string;
  prompt: string;
  copy: string;
  status: StorylineFrameStatus;
  attempt: number;
  asset?: StorylineFrameAsset | null;
  image_job_id?: string | null;
  error?: string | null;
}

export interface StorylineLane {
  lane_id: string;
  model: StorylineModel | string;
  label?: string | null;
  capability_disclosure?: string | null;
  reference_image_limit: number;
  reduced_reference_fidelity: boolean;
  frames: StorylineFrame[];
}

export interface StorylineCreativeDirection {
  summary: string;
  visual_style: string;
  tone: string;
  palette: string[];
  continuity_rules: string[];
}

export interface StorylinePlan {
  plan_id: string;
  version: number;
  creative_direction: StorylineCreativeDirection;
  lanes: StorylineLane[];
}

export interface StorylineModelCapability {
  model: string;
  display_name: string;
  provider: "azure" | "openai" | string;
  max_reference_images: number;
  max_outputs_per_request: number;
  supports_mask: boolean;
  input_fidelity_options: string[];
  output_formats: string[];
  response_format: "b64_json" | "url" | string;
  background_options: string[];
  quality_options: string[];
  recommended_sizes: string[];
  supports_custom_sizes: boolean;
  disclosure: string;
}

export interface Storyline {
  id: string;
  revision: number;
  etag?: string | null;
  client_request_id?: string | null;
  status: StorylineStatus;
  stage: string;
  progress: number;
  title: string;
  settings: StorylineSettings;
  references: StorylineReference[];
  plan?: StorylinePlan | null;
  error?: string | null;
  cancel_requested: boolean;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface StorylineListResponse {
  items: Storyline[];
  total: number;
  limit: number;
  offset: number;
}

export interface StorylineCreateRequest {
  title: string;
  settings: StorylineSettings;
  references?: StorylineReference[];
  idempotency_key?: string;
  client_request_id?: string;
}

export interface StorylineMutationRequest {
  expected_revision?: number;
  expected_etag?: string;
}

export interface StorylinePlanUpdateRequest extends StorylineMutationRequest {
  plan: StorylinePlan;
}

export interface StorylineFrameActionRequest extends StorylineMutationRequest {
  reason?: string;
  prompt?: string;
  copy?: string;
}

export function buildStorylineImagePrompt(
  direction: StorylineCreativeDirection,
  purpose: string,
  framePrompt: string,
): string {
  return [
    "Create one frame from a coherent multi-image campaign.",
    `Creative direction: ${direction.summary}`,
    `Visual style: ${direction.visual_style}`,
    `Tone: ${direction.tone}`,
    `Palette: ${direction.palette.join(", ")}`,
    `Continuity rules:\n- ${direction.continuity_rules.join("\n- ")}`,
    `Narrative purpose: ${purpose}`,
    `Frame instruction: ${framePrompt}`,
    "Keep campaign copy separate from the image. Do not add captions, headlines, labels, or other typography unless the frame instruction explicitly asks for visible text.",
  ].join("\n\n");
}

export function isActiveStoryline(status: StorylineStatus): boolean {
  return ["draft", "planned", "queued", "generating", "cancel_requested"].includes(
    status,
  );
}
