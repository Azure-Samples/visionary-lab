import { API_BASE_URL } from "./api";
import type { ImagePipelineRequest } from "./api";
import {
  IMAGE_JOB_STATUSES,
  type CreateImageJobPayload,
  type ImageJob,
  type ImageJobListResponse,
} from "@/types/image-jobs";

interface ApiErrorBody {
  detail?: unknown;
  message?: unknown;
  error?: unknown;
}

async function getErrorMessage(response: Response): Promise<string> {
  const fallback = `Request failed with ${response.status} ${response.statusText}`;

  try {
    const body = (await response.json()) as ApiErrorBody;
    const detail = body.detail ?? body.message ?? body.error;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (detail !== undefined) return JSON.stringify(detail);
  } catch {
    // The response was not JSON. Fall back to the HTTP status below.
  }

  return fallback;
}

async function fetchJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("Cache-Control", "no-store");
  headers.set("Pragma", "no-cache");

  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return response.json() as Promise<T>;
}

function assertImageJob(value: unknown): ImageJob {
  if (!value || typeof value !== "object") {
    throw new Error("The image job response was malformed");
  }

  const job = value as Partial<ImageJob>;
  if (
    typeof job.id !== "string" ||
    typeof job.status !== "string" ||
    !IMAGE_JOB_STATUSES.includes(job.status as ImageJob["status"])
  ) {
    throw new Error("The image job response was malformed");
  }

  return job as ImageJob;
}

export async function createImageJob(
  request: ImagePipelineRequest,
  idempotencyKey?: string,
  clientRequestId?: string,
  signal?: AbortSignal,
): Promise<ImageJob> {
  const payload: CreateImageJobPayload = {
    request,
    idempotency_key: idempotencyKey,
    client_request_id: clientRequestId,
  };
  const job = await fetchJson<unknown>("/images/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  return assertImageJob(job);
}

export async function listImageJobs(
  options: {
    limit?: number;
    statuses?: ImageJob["status"][];
  } = {},
  signal?: AbortSignal,
): Promise<ImageJobListResponse> {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 50),
  });
  for (const status of options.statuses ?? []) {
    params.append("status", status);
  }
  const response = await fetchJson<ImageJobListResponse>(
    `/images/jobs?${params.toString()}`,
    { signal },
  );

  if (!Array.isArray(response.jobs)) {
    throw new Error("The image jobs response was malformed");
  }

  const jobs = response.jobs
    .map(assertImageJob)
    .filter((job) => !job.storyline_id);
  return {
    ...response,
    jobs,
    total: jobs.length,
  };
}

export async function getImageJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<ImageJob> {
  const job = await fetchJson<unknown>(
    `/images/jobs/${encodeURIComponent(jobId)}`,
    { signal },
  );
  return assertImageJob(job);
}

export async function cancelImageJob(jobId: string): Promise<ImageJob> {
  const job = await fetchJson<unknown>(
    `/images/jobs/${encodeURIComponent(jobId)}`,
    { method: "DELETE" },
  );
  return assertImageJob(job);
}

export async function retryImageJob(jobId: string): Promise<ImageJob> {
  const job = await fetchJson<unknown>(
    `/images/jobs/${encodeURIComponent(jobId)}/retry`,
    { method: "POST" },
  );
  return assertImageJob(job);
}
