"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ImagePipelineRequest } from "@/services/api";
import {
  cancelImageJob,
  createImageJob,
  listImageJobs,
  retryImageJob,
} from "@/services/imageJobs";
import {
  createReservedOutputs,
  isActiveImageJob,
  isTerminalImageJob,
  type ImageJob,
  type ImageJobEntry,
  type ImageJobStatus,
} from "@/types/image-jobs";

const PENDING_STORAGE_KEY = "visionary-lab:image-pending-submissions:v2";
const MAX_VISIBLE_JOBS = 100;
const ACTIVE_POLL_INTERVAL_MS = 2_000;
const ACTIVE_IDLE_INTERVAL_MS = 30_000;
const ACTIVE_ERROR_RETRY_INTERVAL_MS = 8_000;
const RECENT_ACTIVE_INTERVAL_MS = 5_000;
const RECENT_IDLE_INTERVAL_MS = 30_000;

const ACTIVE_STATUSES: ImageJobStatus[] = [
  "queued",
  "generating",
  "saving",
  "analyzing",
  "cancel_requested",
];
const RECENT_STATUSES: ImageJobStatus[] = [
  "completed",
  "partial",
  "failed",
  "cancelled",
];

export type ImageJobMutation = "cancel" | "retry";
export type ImageJobsConnectionState = "connected" | "reconnecting";

interface PendingSubmissionRecord {
  clientRequestId: string;
  idempotencyKey: string;
  request: ImagePipelineRequest;
  createdAt: string;
}

interface ImageJobsContextValue {
  jobs: ImageJobEntry[];
  activeCount: number;
  activeImageCount: number;
  isHydrating: boolean;
  lastError: string | null;
  lastSyncedAt: Date | null;
  connectionState: ImageJobsConnectionState;
  mutationByJobId: Record<string, ImageJobMutation | undefined>;
  submitJob: (
    request: ImagePipelineRequest,
    idempotencyKey?: string,
    clientRequestId?: string,
  ) => Promise<ImageJob>;
  cancelJob: (jobId: string) => Promise<ImageJob>;
  retryJob: (jobId: string) => Promise<ImageJob>;
  refreshJobs: () => Promise<void>;
}

const ImageJobsContext = createContext<ImageJobsContextValue | undefined>(
  undefined,
);

function createClientId(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function parsePendingSubmissions(raw: string | null): PendingSubmissionRecord[] {
  if (!raw) return [];
  try {
    const value = JSON.parse(raw) as unknown;
    if (!Array.isArray(value)) return [];
    return value.flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const record = item as Partial<PendingSubmissionRecord>;
      if (
        typeof record.clientRequestId !== "string" ||
        typeof record.idempotencyKey !== "string" ||
        typeof record.createdAt !== "string" ||
        !record.request ||
        typeof record.request !== "object"
      ) {
        return [];
      }
      return [record as PendingSubmissionRecord];
    });
  } catch {
    return [];
  }
}

function readPendingSubmissions(): PendingSubmissionRecord[] {
  if (typeof window === "undefined") return [];
  try {
    return parsePendingSubmissions(window.localStorage.getItem(PENDING_STORAGE_KEY));
  } catch {
    return [];
  }
}

function createOptimisticJob(
  record: PendingSubmissionRecord,
  status: "submitting" | "submission_failed" = "submitting",
  error?: string,
): ImageJobEntry {
  const request = record.request;
  const requestedImages = Math.max(1, request.n ?? 1);
  const analysisEnabled = Boolean(request.analysis_options.enabled);
  return {
    id: `local:${record.clientRequestId}`,
    revision: 0,
    client_request_id: record.clientRequestId,
    status,
    stage: status === "submitting" ? "Submitting" : "Submission failed",
    progress: 0,
    prompt:
      typeof request.metadata?.original_prompt === "string"
        ? request.metadata.original_prompt
        : request.prompt,
    model: request.model ?? "gpt-image-2",
    folder_path: request.save_options.folder_path ?? "",
    size: request.size ?? "1024x1024",
    analysis_enabled: analysisEnabled,
    requested_images: requestedImages,
    completed_images: 0,
    failed_images: status === "submission_failed" ? requestedImages : 0,
    created_at: record.createdAt,
    updated_at: record.createdAt,
    result: null,
    error: error ?? null,
    cancel_requested: false,
    attempt: 0,
    parent_job_id: null,
    outputs: createReservedOutputs(requestedImages, analysisEnabled),
    local: {
      folderPath: request.save_options.folder_path,
      analyze: analysisEnabled,
      idempotencyKey: record.idempotencyKey,
      request,
      optimistic: true,
      submittedAt: record.createdAt,
    },
  };
}

function normalizeServerJob(job: ImageJob): ImageJob {
  const requestedImages = Math.max(1, job.requested_images || 1);
  const analysisEnabled = Boolean(job.analysis_enabled);
  return {
    ...job,
    revision: Number.isFinite(job.revision) ? job.revision : 0,
    progress: Number.isFinite(job.progress)
      ? Math.max(0, Math.min(100, job.progress))
      : 0,
    folder_path: job.folder_path ?? "",
    size: job.size || "1024x1024",
    analysis_enabled: analysisEnabled,
    attempt: Number.isFinite(job.attempt) ? job.attempt : 0,
    outputs:
      Array.isArray(job.outputs) && job.outputs.length > 0
        ? [...job.outputs]
            .map((output) => ({
              ...output,
              progress: Number.isFinite(output.progress)
                ? Math.max(0, Math.min(100, output.progress))
                : 0,
            }))
            .sort((a, b) => a.index - b.index)
        : createReservedOutputs(requestedImages, analysisEnabled),
  };
}

function sortJobs(jobs: ImageJobEntry[]): ImageJobEntry[] {
  return [...jobs]
    .sort((a, b) => {
      const aActive = isActiveImageJob(a.status);
      const bActive = isActiveImageJob(b.status);
      if (aActive !== bActive) return aActive ? -1 : 1;
      const aTime = Date.parse(a.created_at) || 0;
      const bTime = Date.parse(b.created_at) || 0;
      return bTime - aTime;
    })
    .slice(0, MAX_VISIBLE_JOBS);
}

function shouldAcceptServerUpdate(
  existing: ImageJobEntry,
  incoming: ImageJob,
): boolean {
  if (existing.local?.optimistic) return true;
  if (incoming.revision < existing.revision) return false;
  if (
    incoming.revision === existing.revision &&
    Date.parse(incoming.updated_at) < Date.parse(existing.updated_at)
  ) {
    return false;
  }
  if (
    isTerminalImageJob(existing.status) &&
    existing.status !== "submission_failed" &&
    !isTerminalImageJob(incoming.status)
  ) {
    return false;
  }
  if (
    existing.status === "cancel_requested" &&
    !["cancel_requested", "cancelled", "failed", "partial", "completed"].includes(
      incoming.status,
    )
  ) {
    return false;
  }
  return true;
}

function mergeServerJobs(
  current: ImageJobEntry[],
  incomingJobs: ImageJob[],
): ImageJobEntry[] {
  if (incomingJobs.length === 0) return current;

  const byId = new Map(current.map((job) => [job.id, job]));
  let changed = false;
  for (const rawJob of incomingJobs) {
    const incoming = normalizeServerJob(rawJob);
    const clientMatch = incoming.client_request_id
      ? Array.from(byId.values()).find(
          (job) =>
            job.local?.optimistic &&
            job.client_request_id === incoming.client_request_id,
        )
      : undefined;
    const existing = byId.get(incoming.id) ?? clientMatch;

    if (
      existing &&
      !existing.local?.optimistic &&
      existing.revision === incoming.revision &&
      existing.updated_at === incoming.updated_at
    ) {
      continue;
    }
    if (existing && !shouldAcceptServerUpdate(existing, incoming)) continue;
    if (clientMatch && clientMatch.id !== incoming.id) byId.delete(clientMatch.id);

    byId.set(incoming.id, {
      ...incoming,
      local: existing?.local
        ? {
            ...existing.local,
            folderPath: incoming.folder_path ?? existing.local.folderPath,
            analyze: incoming.analysis_enabled,
            optimistic: false,
            request: undefined,
          }
        : undefined,
    });
    changed = true;
  }
  return changed ? sortJobs(Array.from(byId.values())) : current;
}

export function ImageJobsProvider({ children }: { children: React.ReactNode }) {
  const [jobs, setJobs] = useState<ImageJobEntry[]>([]);
  const [isHydrating, setIsHydrating] = useState(true);
  const [activeError, setActiveError] = useState<string | null>(null);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null);
  const [mutationByJobId, setMutationByJobId] = useState<
    Record<string, ImageJobMutation | undefined>
  >({});
  const jobsRef = useRef(jobs);
  const mutationByJobIdRef = useRef(mutationByJobId);
  const pendingStorageHydratedRef = useRef(false);
  const activeRefreshInFlightRef = useRef(false);
  const recentRefreshInFlightRef = useRef(false);
  const activeControllerRef = useRef<AbortController | null>(null);
  const recentControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

  useEffect(() => {
    mutationByJobIdRef.current = mutationByJobId;
  }, [mutationByJobId]);

  useEffect(() => {
    if (typeof window === "undefined" || !pendingStorageHydratedRef.current) return;
    const pending = jobs.flatMap((job): PendingSubmissionRecord[] => {
      if (
        !job.local?.optimistic ||
        !job.local.request ||
        !job.local.idempotencyKey ||
        !job.client_request_id
      ) {
        return [];
      }
      return [
        {
          clientRequestId: job.client_request_id,
          idempotencyKey: job.local.idempotencyKey,
          request: job.local.request,
          createdAt: job.local.submittedAt ?? job.created_at,
        },
      ];
    });
    try {
      window.localStorage.setItem(PENDING_STORAGE_KEY, JSON.stringify(pending));
    } catch {
      // Private browsing can disable storage; the in-memory queue still works.
    }
  }, [jobs]);

  const mergeJobs = useCallback((incoming: ImageJob[]) => {
    setJobs((current) => mergeServerJobs(current, incoming));
  }, []);

  const refreshRecentJobs = useCallback(async () => {
    if (recentRefreshInFlightRef.current) return;
    recentRefreshInFlightRef.current = true;
    const controller = new AbortController();
    recentControllerRef.current = controller;
    try {
      const response = await listImageJobs(
        { limit: 50, statuses: RECENT_STATUSES },
        controller.signal,
      );
      mergeJobs(response.jobs);
      setRecentError(null);
      setLastSyncedAt(new Date());
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      setRecentError(
        error instanceof Error ? error.message : "Unable to refresh recent image jobs",
      );
    } finally {
      if (recentControllerRef.current === controller) {
        recentControllerRef.current = null;
      }
      recentRefreshInFlightRef.current = false;
    }
  }, [mergeJobs]);

  const refreshActiveJobs = useCallback(async () => {
    if (activeRefreshInFlightRef.current) return;
    activeRefreshInFlightRef.current = true;
    const controller = new AbortController();
    activeControllerRef.current = controller;
    try {
      const response = await listImageJobs(
        { limit: 100, statuses: ACTIVE_STATUSES },
        controller.signal,
      );
      const incomingIds = new Set(response.jobs.map((job) => job.id));
      const activeServerJobs = jobsRef.current.filter(
        (job) => isActiveImageJob(job.status) && !job.local?.optimistic,
      );
      const activeJobDisappeared = activeServerJobs.some(
        (job) => !incomingIds.has(job.id),
      );
      mergeJobs(response.jobs);
      setActiveError(null);
      setLastSyncedAt(new Date());
      if (activeJobDisappeared) void refreshRecentJobs();
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      setActiveError(
        error instanceof Error ? error.message : "Unable to refresh active image jobs",
      );
    } finally {
      if (activeControllerRef.current === controller) {
        activeControllerRef.current = null;
      }
      activeRefreshInFlightRef.current = false;
    }
  }, [mergeJobs, refreshRecentJobs]);

  const refreshJobs = useCallback(async () => {
    await Promise.allSettled([refreshActiveJobs(), refreshRecentJobs()]);
  }, [refreshActiveJobs, refreshRecentJobs]);

  const reconcileSubmission = useCallback(
    async (record: PendingSubmissionRecord): Promise<ImageJob> => {
      const responseJob = await createImageJob(
        record.request,
        record.idempotencyKey,
        record.clientRequestId,
      );
      const job: ImageJob = {
        ...responseJob,
        client_request_id: responseJob.client_request_id ?? record.clientRequestId,
      };
      mergeJobs([job]);
      setActiveError(null);
      setLastSyncedAt(new Date());
      return job;
    },
    [mergeJobs],
  );

  useEffect(() => {
    let cancelled = false;
    const hydrate = async () => {
      const pending = readPendingSubmissions();
      pendingStorageHydratedRef.current = true;
      if (pending.length > 0) {
        setJobs((current) =>
          sortJobs([
            ...pending.map((record) => createOptimisticJob(record)),
            ...current,
          ]),
        );
      }
      await refreshJobs();
      await Promise.allSettled(
        pending.map(async (record) => {
          try {
            await reconcileSubmission(record);
          } catch (error) {
            if (cancelled) return;
            const message = error instanceof Error ? error.message : "Submission failed";
            setJobs((current) =>
              current.map((job) =>
                job.client_request_id === record.clientRequestId && job.local?.optimistic
                  ? {
                      ...job,
                      status: "submission_failed" as const,
                      stage: "Submission failed",
                      error: message,
                      failed_images: job.requested_images,
                    }
                  : job,
              ),
            );
          }
        }),
      );
      if (!cancelled) setIsHydrating(false);
    };
    void hydrate();
    return () => {
      cancelled = true;
      activeControllerRef.current?.abort();
      recentControllerRef.current?.abort();
    };
  }, [reconcileSubmission, refreshJobs]);

  const activeCount = useMemo(
    () => jobs.filter((job) => isActiveImageJob(job.status)).length,
    [jobs],
  );
  const activeImageCount = useMemo(
    () =>
      jobs
        .filter((job) => isActiveImageJob(job.status))
        .reduce(
          (total, job) =>
            total +
            job.outputs.filter(
              (output) =>
                !["ready", "failed", "cancelled"].includes(output.status),
            ).length,
          0,
        ),
    [jobs],
  );
  const optimisticCount = useMemo(
    () => jobs.filter((job) => job.status === "submitting").length,
    [jobs],
  );

  useEffect(() => {
    const pollInterval = activeError
      ? ACTIVE_ERROR_RETRY_INTERVAL_MS
      : activeCount > 0 || optimisticCount > 0
        ? ACTIVE_POLL_INTERVAL_MS
        : ACTIVE_IDLE_INTERVAL_MS;
    const intervalId = window.setInterval(() => {
      if (document.visibilityState === "visible") void refreshActiveJobs();
    }, pollInterval);
    return () => window.clearInterval(intervalId);
  }, [activeCount, activeError, optimisticCount, refreshActiveJobs]);

  useEffect(() => {
    const pollInterval = activeCount > 0
      ? RECENT_ACTIVE_INTERVAL_MS
      : RECENT_IDLE_INTERVAL_MS;
    const intervalId = window.setInterval(() => {
      if (document.visibilityState === "visible") void refreshRecentJobs();
    }, pollInterval);
    return () => window.clearInterval(intervalId);
  }, [activeCount, refreshRecentJobs]);

  useEffect(() => {
    const refreshVisibleJobs = () => {
      if (document.visibilityState === "visible") void refreshJobs();
    };
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== PENDING_STORAGE_KEY) return;
      const pending = parsePendingSubmissions(event.newValue);
      setJobs((current) => {
        const existingClientIds = new Set(
          current.map((job) => job.client_request_id).filter(Boolean),
        );
        const additions = pending
          .filter((record) => !existingClientIds.has(record.clientRequestId))
          .map((record) => createOptimisticJob(record));
        return additions.length > 0 ? sortJobs([...additions, ...current]) : current;
      });
      for (const record of pending) {
        void reconcileSubmission(record).catch(() => {
          // The submitting tab or the reconnect poll may still reconcile it.
        });
      }
      void refreshJobs();
    };
    document.addEventListener("visibilitychange", refreshVisibleJobs);
    window.addEventListener("online", refreshVisibleJobs);
    window.addEventListener("storage", handleStorage);
    return () => {
      document.removeEventListener("visibilitychange", refreshVisibleJobs);
      window.removeEventListener("online", refreshVisibleJobs);
      window.removeEventListener("storage", handleStorage);
    };
  }, [reconcileSubmission, refreshJobs]);

  const submitJob = useCallback(
    async (
      request: ImagePipelineRequest,
      idempotencyKey = createClientId("image"),
      clientRequestId = idempotencyKey,
    ) => {
      const record: PendingSubmissionRecord = {
        clientRequestId,
        idempotencyKey,
        request,
        createdAt: new Date().toISOString(),
      };
      const optimisticJob = createOptimisticJob(record);
      setJobs((current) =>
        sortJobs([
          optimisticJob,
          ...current.filter(
            (job) => job.client_request_id !== optimisticJob.client_request_id,
          ),
        ]),
      );
      try {
        return await reconcileSubmission(record);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to submit image job";
        setJobs((current) =>
          current.map((job) =>
            job.client_request_id === clientRequestId && job.local?.optimistic
              ? {
                  ...job,
                  status: "submission_failed" as const,
                  stage: "Submission failed",
                  error: message,
                  failed_images: job.requested_images,
                }
              : job,
          ),
        );
        void refreshActiveJobs();
        throw error;
      }
    },
    [reconcileSubmission, refreshActiveJobs],
  );

  const setMutation = useCallback(
    (jobId: string, mutation?: ImageJobMutation) => {
      const nextRef = { ...mutationByJobIdRef.current };
      if (mutation) nextRef[jobId] = mutation;
      else delete nextRef[jobId];
      mutationByJobIdRef.current = nextRef;
      setMutationByJobId((current) => {
        const next = { ...current };
        if (mutation) next[jobId] = mutation;
        else delete next[jobId];
        return next;
      });
    },
    [],
  );

  const cancelJob = useCallback(
    async (jobId: string) => {
      if (mutationByJobIdRef.current[jobId]) {
        throw new Error("An action is already in progress for this generation");
      }
      const before = jobsRef.current.find((job) => job.id === jobId);
      if (!before || before.local?.optimistic) {
        throw new Error("This generation has not reached the server yet");
      }
      setMutation(jobId, "cancel");
      setJobs((current) =>
        current.map((job) =>
          job.id === jobId
            ? {
                ...job,
                status: "cancel_requested" as const,
                stage: "cancel_requested",
                cancel_requested: true,
              }
            : job,
        ),
      );
      try {
        const job = await cancelImageJob(jobId);
        mergeJobs([job]);
        return job;
      } catch (error) {
        setJobs((current) =>
          current.map((job) =>
            job.id === jobId && job.revision === before.revision ? before : job,
          ),
        );
        throw error;
      } finally {
        setMutation(jobId);
      }
    },
    [mergeJobs, setMutation],
  );

  const retryJob = useCallback(
    async (jobId: string) => {
      if (mutationByJobIdRef.current[jobId]) {
        throw new Error("An action is already in progress for this generation");
      }
      const existing = jobsRef.current.find((job) => job.id === jobId);
      if (!existing) throw new Error("Image generation was not found");
      setMutation(jobId, "retry");
      try {
        if (
          existing.status === "submission_failed" &&
          existing.local?.request &&
          existing.local.idempotencyKey &&
          existing.client_request_id
        ) {
          setJobs((current) =>
            current.map((job) =>
              job.id === jobId
                ? { ...job, status: "submitting" as const, stage: "Submitting", error: null }
                : job,
            ),
          );
          try {
            return await reconcileSubmission({
              clientRequestId: existing.client_request_id,
              idempotencyKey: existing.local.idempotencyKey,
              request: existing.local.request,
              createdAt: existing.local.submittedAt ?? existing.created_at,
            });
          } catch (error) {
            const message = error instanceof Error ? error.message : "Submission failed";
            setJobs((current) =>
              current.map((job) =>
                job.id === jobId
                  ? {
                      ...job,
                      status: "submission_failed" as const,
                      stage: "Submission failed",
                      error: message,
                    }
                  : job,
              ),
            );
            void refreshActiveJobs();
            throw error;
          }
        }
        const job = await retryImageJob(jobId);
        mergeJobs([job]);
        return job;
      } finally {
        setMutation(jobId);
      }
    },
    [mergeJobs, reconcileSubmission, refreshActiveJobs, setMutation],
  );

  const lastError = activeError ?? recentError;
  const connectionState: ImageJobsConnectionState = lastError
    ? "reconnecting"
    : "connected";
  const value = useMemo<ImageJobsContextValue>(
    () => ({
      jobs,
      activeCount,
      activeImageCount,
      isHydrating,
      lastError,
      lastSyncedAt,
      connectionState,
      mutationByJobId,
      submitJob,
      cancelJob,
      retryJob,
      refreshJobs,
    }),
    [
      jobs,
      activeCount,
      activeImageCount,
      isHydrating,
      lastError,
      lastSyncedAt,
      connectionState,
      mutationByJobId,
      submitJob,
      cancelJob,
      retryJob,
      refreshJobs,
    ],
  );

  return (
    <ImageJobsContext.Provider value={value}>
      {children}
    </ImageJobsContext.Provider>
  );
}

export function useImageJobs(): ImageJobsContextValue {
  const context = useContext(ImageJobsContext);
  if (!context) {
    throw new Error("useImageJobs must be used within an ImageJobsProvider");
  }
  return context;
}
