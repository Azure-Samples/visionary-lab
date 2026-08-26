import { API_BASE_URL } from "@/services/api";
import type {
  Storyline,
  StorylineCreateRequest,
  StorylineFrame,
  StorylineFrameActionRequest,
  StorylineFrameStatus,
  StorylineLane,
  StorylineListResponse,
  StorylineModelCapability,
  StorylinePlan,
  StorylinePlanUpdateRequest,
  StorylineReference,
  StorylineSettings,
  StorylineStatus,
} from "@/types/storyline";
import {
  STORYLINE_FRAME_STATUSES,
  STORYLINE_STATUSES,
} from "@/types/storyline";

const STORYLINES_PATH = "/storylines";

interface ApiErrorBody {
  detail?: unknown;
  message?: unknown;
  error?: unknown;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function normalizeStatus(value: unknown): StorylineStatus {
  return typeof value === "string" &&
    STORYLINE_STATUSES.includes(value as StorylineStatus)
    ? (value as StorylineStatus)
    : "draft";
}

function normalizeFrameStatus(value: unknown): StorylineFrameStatus {
  return typeof value === "string" &&
    STORYLINE_FRAME_STATUSES.includes(value as StorylineFrameStatus)
    ? (value as StorylineFrameStatus)
    : "pending";
}

function normalizeSettings(value: unknown): StorylineSettings {
  const settings = asRecord(value);
  return {
    prompt: asString(settings.prompt),
    frame_count: Math.max(2, Math.min(10, asNumber(settings.frame_count, 4))),
    models: Array.isArray(settings.models)
      ? settings.models.filter(
          (model): model is StorylineSettings["models"][number] =>
            typeof model === "string" && model.length > 0,
        )
      : ["gpt-image-2"],
    channel: asString(settings.channel, "instagram"),
    copy_depth:
      settings.copy_depth === "punchy" || settings.copy_depth === "detailed"
        ? settings.copy_depth
        : "balanced",
    size: asString(settings.size, "1024x1024"),
    quality: asString(settings.quality, "high"),
    background: asString(settings.background, "auto"),
    output_format: asString(settings.output_format, "png"),
    output_compression: asNumber(settings.output_compression, 100),
    input_fidelity: settings.input_fidelity === "low" ? "low" : "high",
    review_plan_first: settings.review_plan_first === true,
    folder_path: asString(settings.folder_path) || null,
    analysis_enabled: Boolean(settings.analysis_enabled),
  };
}

function normalizeReference(value: unknown, index: number): StorylineReference {
  const reference = asRecord(value);
  return {
    reference_id: asString(reference.reference_id, `reference-${index}`),
    blob_name: asString(reference.blob_name),
    url: asString(reference.url),
    container: asString(reference.container, "images"),
    content_type: asString(reference.content_type, "image/png"),
    original_filename: asString(
      reference.original_filename,
      asString(reference.blob_name, `reference-${index}`),
    ),
    order: Math.max(1, asNumber(reference.order, index)),
  };
}

function normalizeFrame(value: unknown, laneId: string, index: number): StorylineFrame {
  const frame = asRecord(value);
  const asset = asRecord(frame.asset);
  return {
    frame_id: asString(frame.frame_id, `frame-${laneId}-${index}`),
    plan_frame_id: asString(frame.plan_frame_id, `plan-frame-${index}`),
    lane_id: asString(frame.lane_id, laneId),
    order: Math.max(1, asNumber(frame.order, index)),
    title: asString(frame.title) || null,
    purpose: asString(frame.purpose, `Frame ${index}`),
    prompt: asString(frame.prompt),
    copy: asString(frame.copy ?? frame.copy_text),
    status: normalizeFrameStatus(frame.status),
    attempt: Math.max(0, asNumber(frame.attempt, 0)),
    asset:
      Object.keys(asset).length > 0
        ? {
            ...asset,
            blob_name: asString(asset.blob_name),
            url: asString(asset.url),
          }
        : null,
    image_job_id: asString(frame.image_job_id) || null,
    error: asString(frame.error) || null,
  };
}

function normalizeLane(value: unknown, index: number): StorylineLane {
  const lane = asRecord(value);
  const laneId = asString(lane.lane_id, `lane-${index}`);
  const frames = Array.isArray(lane.frames) ? lane.frames : [];
  return {
    lane_id: laneId,
    model: asString(lane.model, "gpt-image-2"),
    label: asString(lane.label) || null,
    capability_disclosure: asString(lane.capability_disclosure) || null,
    reference_image_limit: Math.max(0, asNumber(lane.reference_image_limit, 10)),
    reduced_reference_fidelity: Boolean(lane.reduced_reference_fidelity),
    frames: frames
      .map((frame, frameIndex) => normalizeFrame(frame, laneId, frameIndex + 1))
      .sort((a, b) => a.order - b.order),
  };
}

function normalizePlan(value: unknown): StorylinePlan | null {
  const plan = asRecord(value);
  if (Object.keys(plan).length === 0) return null;
  const lanes = Array.isArray(plan.lanes) ? plan.lanes : [];
  const direction = asRecord(plan.creative_direction);
  return {
    plan_id: asString(plan.plan_id, "plan"),
    version: Math.max(1, asNumber(plan.version, 1)),
    creative_direction: {
      summary: asString(direction.summary),
      visual_style: asString(direction.visual_style),
      tone: asString(direction.tone),
      palette: Array.isArray(direction.palette)
        ? direction.palette.filter((item): item is string => typeof item === "string")
        : [],
      continuity_rules: Array.isArray(direction.continuity_rules)
        ? direction.continuity_rules.filter(
            (item): item is string => typeof item === "string",
          )
        : [],
    },
    lanes: lanes.map((lane, index) => normalizeLane(lane, index + 1)),
  };
}

export function normalizeStoryline(value: unknown): Storyline {
  const outer = asRecord(value);
  const record = asRecord(outer.storyline ?? outer.result ?? value);
  const settings = normalizeSettings(record.settings);
  const createdAt = asString(record.created_at, new Date().toISOString());
  return {
    id: asString(record.id ?? record.storyline_id),
    revision: Math.max(1, asNumber(record.revision, 1)),
    etag: asString(record.etag) || null,
    client_request_id: asString(record.client_request_id) || null,
    status: normalizeStatus(record.status),
    stage: asString(record.stage, normalizeStatus(record.status)),
    progress: Math.max(0, Math.min(100, asNumber(record.progress, 0))),
    title: asString(record.title, "Untitled storyline"),
    settings,
    references: Array.isArray(record.references)
      ? record.references.map((reference, index) =>
          normalizeReference(reference, index + 1),
        )
      : [],
    plan: normalizePlan(record.plan),
    error: asString(record.error) || null,
    cancel_requested: Boolean(record.cancel_requested),
    created_at: createdAt,
    updated_at: asString(record.updated_at, createdAt),
    completed_at: asString(record.completed_at) || null,
  };
}

async function getErrorMessage(response: Response): Promise<string> {
  const fallback = `Request failed with ${response.status} ${response.statusText}`;
  try {
    const body = (await response.json()) as ApiErrorBody;
    const detail = body.detail ?? body.message ?? body.error;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (detail !== undefined) return JSON.stringify(detail);
  } catch {
    // Use the HTTP fallback when the response is not JSON.
  }
  return fallback;
}

async function fetchJson(path: string, init: RequestInit = {}): Promise<unknown> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("Cache-Control", "no-store");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers,
  });
  if (!response.ok) throw new Error(await getErrorMessage(response));
  return response.json() as Promise<unknown>;
}

function mutationPreconditions(storyline: Storyline): StorylineFrameActionRequest {
  return {
    expected_revision: storyline.revision,
    ...(storyline.etag ? { expected_etag: storyline.etag } : {}),
  };
}

export async function uploadStorylineReferences(
  files: File[],
): Promise<StorylineReference[]> {
  const uploaded: StorylineReference[] = [];
  try {
    for (const [index, file] of files.entries()) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("order", String(index + 1));
      const value = await fetchJson(`${STORYLINES_PATH}/references`, {
        method: "POST",
        body: formData,
      });
      uploaded.push(normalizeReference(value, index + 1));
    }
    return uploaded;
  } catch (error) {
    await Promise.allSettled(
      uploaded.map((reference) => {
        const params = new URLSearchParams({
          blob_name: reference.blob_name,
          media_type: "image",
        });
        return fetchJson(`/gallery/delete?${params.toString()}`, {
          method: "DELETE",
        });
      }),
    );
    throw error instanceof Error
      ? error
      : new Error("One or more reference images could not be uploaded");
  }
}

export async function createStoryline(
  request: StorylineCreateRequest,
): Promise<Storyline> {
  const value = await fetchJson(STORYLINES_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  const storyline = normalizeStoryline(value);
  if (!storyline.id) throw new Error("The storyline response did not include an ID");
  return storyline;
}

export async function listStorylines(
  options: { limit?: number; offset?: number; statuses?: StorylineStatus[] } = {},
): Promise<StorylineListResponse> {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 50),
    offset: String(options.offset ?? 0),
  });
  for (const status of options.statuses ?? []) params.append("status", status);
  const value = await fetchJson(`${STORYLINES_PATH}?${params.toString()}`);
  const record = asRecord(value);
  const rawItems = Array.isArray(record.items) ? record.items : [];
  return {
    items: rawItems.map(normalizeStoryline),
    total: asNumber(record.total, rawItems.length),
    limit: asNumber(record.limit, options.limit ?? 50),
    offset: asNumber(record.offset, options.offset ?? 0),
  };
}

export async function getStoryline(storylineId: string): Promise<Storyline> {
  return normalizeStoryline(
    await fetchJson(`${STORYLINES_PATH}/${encodeURIComponent(storylineId)}`),
  );
}

export async function updateStorylinePlan(
  storyline: Storyline,
  plan: StorylinePlan,
): Promise<Storyline> {
  const request: StorylinePlanUpdateRequest = {
    plan,
    ...mutationPreconditions(storyline),
  };
  return normalizeStoryline(
    await fetchJson(`${STORYLINES_PATH}/${encodeURIComponent(storyline.id)}/plan`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }),
  );
}

export async function cancelStoryline(storyline: Storyline): Promise<Storyline> {
  return normalizeStoryline(
    await fetchJson(`${STORYLINES_PATH}/${encodeURIComponent(storyline.id)}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(mutationPreconditions(storyline)),
    }),
  );
}

export async function regenerateStorylineFrame(
  storyline: Storyline,
  frameId: string,
  overrides: { prompt?: string; copy?: string } = {},
): Promise<Storyline> {
  return normalizeStoryline(
    await fetchJson(
      `${STORYLINES_PATH}/${encodeURIComponent(storyline.id)}/frames/${encodeURIComponent(frameId)}/regenerate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...mutationPreconditions(storyline), ...overrides }),
      },
    ),
  );
}

export async function retryStorylineFrame(
  storyline: Storyline,
  frameId: string,
): Promise<Storyline> {
  return normalizeStoryline(
    await fetchJson(
      `${STORYLINES_PATH}/${encodeURIComponent(storyline.id)}/frames/${encodeURIComponent(frameId)}/retry`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mutationPreconditions(storyline)),
      },
    ),
  );
}

export async function startStoryline(storyline: Storyline): Promise<Storyline> {
  return normalizeStoryline(
    await fetchJson(`${STORYLINES_PATH}/${encodeURIComponent(storyline.id)}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(mutationPreconditions(storyline)),
    }),
  );
}

export async function retryStorylinePlanning(
  storyline: Storyline,
): Promise<Storyline> {
  return normalizeStoryline(
    await fetchJson(
      `${STORYLINES_PATH}/${encodeURIComponent(storyline.id)}/planning/retry`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mutationPreconditions(storyline)),
      },
    ),
  );
}

export async function getStorylineCapabilities(): Promise<StorylineModelCapability[]> {
  const value = await fetchJson(`${STORYLINES_PATH}/capabilities`);
  const record = asRecord(value);
  const rawItems = Array.isArray(record.items)
    ? record.items
    : Array.isArray(record.models)
      ? record.models
      : Array.isArray(value)
        ? value
        : [];
  return rawItems.flatMap((item): StorylineModelCapability[] => {
    const capability = asRecord(item);
    const model = asString(capability.model);
    if (!model) return [];
    return [
      {
        model,
        display_name: asString(capability.display_name, model),
        provider: asString(capability.provider, "azure"),
        max_reference_images: Math.max(
          0,
          asNumber(capability.max_reference_images, 0),
        ),
        max_outputs_per_request: Math.max(
          1,
          asNumber(capability.max_outputs_per_request, 1),
        ),
        supports_mask: Boolean(capability.supports_mask),
        input_fidelity_options: Array.isArray(capability.input_fidelity_options)
          ? capability.input_fidelity_options.filter(
              (entry): entry is string => typeof entry === "string",
            )
          : [],
        output_formats: Array.isArray(capability.output_formats)
          ? capability.output_formats.filter(
              (entry): entry is string => typeof entry === "string",
            )
          : [],
        response_format: asString(capability.response_format, "b64_json"),
        background_options: Array.isArray(capability.background_options)
          ? capability.background_options.filter(
              (entry): entry is string => typeof entry === "string",
            )
          : [],
        quality_options: Array.isArray(capability.quality_options)
          ? capability.quality_options.filter(
              (entry): entry is string => typeof entry === "string",
            )
          : [],
        recommended_sizes: Array.isArray(capability.recommended_sizes)
          ? capability.recommended_sizes.filter(
              (entry): entry is string => typeof entry === "string",
            )
          : [],
        supports_custom_sizes: Boolean(capability.supports_custom_sizes),
        disclosure: asString(capability.disclosure),
      },
    ];
  });
}
