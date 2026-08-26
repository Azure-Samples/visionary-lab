import type {
  ImagePipelineRequest,
  ImageSaveResponse,
} from "@/services/api";

export const IMAGE_JOB_STATUSES = [
  "queued",
  "generating",
  "saving",
  "analyzing",
  "completed",
  "partial",
  "failed",
  "cancel_requested",
  "cancelled",
] as const;

export type ImageJobStatus = (typeof IMAGE_JOB_STATUSES)[number];

export const IMAGE_OUTPUT_STATUSES = [
  "queued",
  "generating",
  "saving",
  "ready",
  "failed",
  "cancelled",
] as const;

export type ImageOutputStatus = (typeof IMAGE_OUTPUT_STATUSES)[number];

export const IMAGE_ANALYSIS_STATUSES = [
  "not_requested",
  "pending",
  "analyzing",
  "completed",
  "failed",
] as const;

export type ImageAnalysisStatus = (typeof IMAGE_ANALYSIS_STATUSES)[number];

export interface ImageJobOutputAsset {
  blob_name: string;
  url: string;
  original_filename?: string;
  width?: number;
  height?: number;
  [key: string]: unknown;
}

export interface ImageJobOutput {
  index: number;
  status: ImageOutputStatus;
  progress: number;
  asset?: ImageJobOutputAsset | null;
  error?: string | null;
  analysis_status: ImageAnalysisStatus;
}

export interface ImageJob {
  id: string;
  revision: number;
  client_request_id?: string | null;
  storyline_id?: string | null;
  status: ImageJobStatus;
  stage: string;
  progress: number;
  prompt: string;
  model: string;
  folder_path?: string | null;
  size: string;
  analysis_enabled: boolean;
  requested_images: number;
  completed_images: number;
  failed_images: number;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  result?: ImageSaveResponse | null;
  error?: string | null;
  cancel_requested: boolean;
  attempt: number;
  parent_job_id?: string | null;
  outputs: ImageJobOutput[];
}

export interface CreateImageJobPayload {
  request: ImagePipelineRequest;
  idempotency_key?: string;
  client_request_id?: string;
}

export interface ImageJobListResponse {
  jobs: ImageJob[];
  total: number;
}

export interface ImageJobLocalMetadata {
  folderPath?: string;
  analyze?: boolean;
  idempotencyKey?: string;
  request?: ImagePipelineRequest;
  optimistic?: boolean;
  submittedAt?: string;
}

export type LocalImageJobStatus = "submitting" | "submission_failed";
export type ImageJobEntryStatus = ImageJobStatus | LocalImageJobStatus;

export interface ImageJobEntry extends Omit<ImageJob, "status"> {
  status: ImageJobEntryStatus;
  local?: ImageJobLocalMetadata;
}

export function isActiveImageJob(status: ImageJobEntryStatus): boolean {
  return [
    "submitting",
    "queued",
    "generating",
    "saving",
    "analyzing",
    "cancel_requested",
  ].includes(status);
}

export function isTerminalImageJob(status: ImageJobEntryStatus): boolean {
  return !isActiveImageJob(status);
}

export function isFailedImageJob(status: ImageJobEntryStatus): boolean {
  return status === "failed" || status === "submission_failed";
}

function findErrorMessage(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (!value || typeof value !== "object") return null;

  const record = value as Record<string, unknown>;
  for (const key of ["message", "detail", "error"]) {
    const message = findErrorMessage(record[key]);
    if (message) return message;
  }
  return null;
}

export function formatImageJobError(error?: string | null): string | null {
  const raw = error?.trim();
  if (!raw) return null;

  const withoutStatus = raw.replace(/^Error code:\s*\d+\s*-\s*/i, "").trim();
  for (const candidate of [raw, withoutStatus]) {
    try {
      const parsed = JSON.parse(candidate) as unknown;
      const message = findErrorMessage(parsed);
      if (message) return message.slice(0, 240);
    } catch {
      // Some providers serialize Python-style dictionaries instead of JSON.
    }
  }

  const fieldMatch = withoutStatus.match(
    /["'](?:message|detail)["']\s*:\s*(["'])([\s\S]*?)\1(?:\s*[,}])/i,
  );
  if (fieldMatch?.[2]) {
    return fieldMatch[2].replace(/\\(["'])/g, "$1").trim().slice(0, 240);
  }

  const simpleErrorMatch = withoutStatus.match(
    /["']error["']\s*:\s*(["'])([\s\S]*?)\1(?:\s*[,}])/i,
  );
  if (simpleErrorMatch?.[2]) {
    return simpleErrorMatch[2].replace(/\\(["'])/g, "$1").trim().slice(0, 240);
  }

  if (/^[{[]/.test(withoutStatus)) {
    return "The image provider rejected this request.";
  }
  return withoutStatus.slice(0, 240);
}

export function createReservedOutputs(
  count: number,
  analysisEnabled: boolean,
): ImageJobOutput[] {
  return Array.from({ length: Math.max(1, count) }, (_, index) => ({
    index: index + 1,
    status: "queued",
    progress: 0,
    analysis_status: analysisEnabled ? "pending" : "not_requested",
  }));
}
