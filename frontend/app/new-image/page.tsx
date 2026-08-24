"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { Clock, FolderIcon, ImageIcon, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { ImageCreationContainer } from "@/components/ImageCreationContainer";
import { ImageDetailView } from "@/components/ImageDetailView";
import { ImageGalleryCard } from "@/components/image-gallery-card";
import { ImageJobOutputCard } from "@/components/image-job-output-card";
import { ImageJobsInline } from "@/components/image-jobs-activity";
import { PageHeader } from "@/components/page-header";
import { RowBasedMasonryGrid } from "@/components/RowBasedMasonryGrid";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useImageJobs } from "@/context/image-jobs-context";
import { isActiveImageJob } from "@/types/image-jobs";
import { fetchImages, type ImageMetadata } from "@/utils/gallery-utils";

const PageTransition = dynamic(
  () =>
    import("@/components/ui/page-transition").then((module) => ({
      default: module.PageTransition,
    })),
  { ssr: false },
);

const PAGE_SIZE = 50;

function normalizeFolder(folderPath?: string | null): string {
  return !folderPath || folderPath === "root" ? "" : folderPath;
}

function GallerySkeletons() {
  return (
    <RowBasedMasonryGrid columns={3} gap={4}>
      {Array.from({ length: 16 }, (_, index) => (
        <Card
          key={`skeleton-${index}`}
          className="h-full w-full overflow-hidden rounded-xl border-0"
        >
          <AspectRatio
            ratio={index % 5 === 0 ? 16 / 9 : index % 3 === 0 ? 3 / 4 : 4 / 3}
            className="bg-muted"
          >
            <Skeleton className="h-full w-full rounded-none" />
          </AspectRatio>
          <div className="space-y-2 p-3">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </Card>
      ))}
    </RowBasedMasonryGrid>
  );
}

function NewImagePageContent() {
  const searchParams = useSearchParams();
  const folderPath = searchParams.get("folder");
  const currentFolder = normalizeFolder(folderPath);
  const { jobs, isHydrating: areJobsHydrating } = useImageJobs();

  const [images, setImages] = useState<ImageMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [lastRefreshedText, setLastRefreshedText] = useState("Never refreshed");
  const [fullscreenImage, setFullscreenImage] = useState<ImageMetadata | null>(null);

  const offsetRef = useRef(0);
  const requestSequenceRef = useRef(0);
  const completionTrackingReadyRef = useRef(false);
  const seenCompletionsRef = useRef(new Set<string>());
  const [pageSessionStartedAt] = useState(() => Date.now());

  const galleryBlobNames = useMemo(
    () => new Set(images.map((image) => image.name)),
    [images],
  );
  const jobOutputCards = useMemo(
    () => {
      const supersededJobIds = new Set(
        jobs.flatMap((job) => (job.parent_job_id ? [job.parent_job_id] : [])),
      );
      return jobs.flatMap((job) => {
        const active = isActiveImageJob(job.status);
        const jobFolder = normalizeFolder(
          job.folder_path ?? job.local?.folderPath,
        );
        if (
          jobFolder !== currentFolder ||
          job.status === "cancelled"
        ) {
          return [];
        }
        const isFreshTerminalUpdate =
          Date.parse(job.completed_at ?? job.updated_at) >=
          pageSessionStartedAt - 60_000;
        const isFreshCompletion =
          (job.status === "completed" || job.status === "partial") &&
          isFreshTerminalUpdate;

        return job.outputs.flatMap((output) => {
          if (supersededJobIds.has(job.id) && output.status !== "ready") {
            return [];
          }
          if (
            output.status === "ready" &&
            output.asset?.blob_name &&
            galleryBlobNames.has(output.asset.blob_name) &&
            !active
          ) {
            return [];
          }
          const shouldShow =
            active ||
            job.status === "submission_failed" ||
            ((job.status === "failed" || job.status === "partial") &&
              isFreshTerminalUpdate) ||
            (output.status === "failed" && isFreshTerminalUpdate) ||
            (output.status === "ready" && isFreshCompletion);
          return shouldShow ? [{ job, output }] : [];
        });
      });
    },
    [currentFolder, galleryBlobNames, jobs, pageSessionStartedAt],
  );
  const visibleOutputBlobNames = useMemo(
    () =>
      new Set(
        jobOutputCards.flatMap(({ output }) =>
          output.asset?.blob_name ? [output.asset.blob_name] : [],
        ),
      ),
    [jobOutputCards],
  );
  const visibleImages = useMemo(
    () => images.filter((image) => !visibleOutputBlobNames.has(image.name)),
    [images, visibleOutputBlobNames],
  );

  const loadImages = useCallback(
    async (reset = true, background = false): Promise<boolean> => {
      const sequence = ++requestSequenceRef.current;
      const requestedOffset = reset ? 0 : offsetRef.current;

      if (reset) {
        if (background) setIsRefreshing(true);
        else setLoading(true);
      } else {
        setIsLoadingMore(true);
      }

      try {
        const fetchedImages = await fetchImages(
          PAGE_SIZE,
          requestedOffset,
          folderPath || undefined,
        );
        if (sequence !== requestSequenceRef.current) return false;

        if (reset) {
          setImages(fetchedImages);
        } else {
          setImages((current) => {
            const existingIds = new Set(current.map((image) => image.id));
            return [
              ...current,
              ...fetchedImages.filter((image) => !existingIds.has(image.id)),
            ];
          });
        }

        offsetRef.current = requestedOffset + fetchedImages.length;
        setHasMore(fetchedImages.length >= PAGE_SIZE);

        if (reset) {
          const now = new Date();
          setLastRefreshed(now);
          setLastRefreshedText(
            `Last refreshed ${formatDistanceToNow(now, { addSuffix: true })}`,
          );
        }
        return true;
      } catch (error) {
        if (sequence !== requestSequenceRef.current) return false;
        console.error("Failed to load images:", error);
        toast.error("Error loading images", {
          description: "Failed to load images from the gallery",
        });
        return false;
      } finally {
        if (sequence === requestSequenceRef.current) {
          setLoading(false);
          setIsLoadingMore(false);
          setIsRefreshing(false);
        }
      }
    },
    [folderPath],
  );

  useEffect(() => {
    offsetRef.current = 0;
    setImages([]);
    void loadImages(true);
  }, [loadImages]);

  useEffect(() => {
    if (!autoRefresh) return;
    const intervalId = window.setInterval(() => {
      void loadImages(true, true);
    }, 30_000);
    return () => window.clearInterval(intervalId);
  }, [autoRefresh, loadImages]);

  useEffect(() => {
    if (!lastRefreshed) return;
    const updateLabel = () => {
      setLastRefreshedText(
        `Last refreshed ${formatDistanceToNow(lastRefreshed, { addSuffix: true })}`,
      );
    };
    const intervalId = window.setInterval(updateLabel, 60_000);
    return () => window.clearInterval(intervalId);
  }, [lastRefreshed]);

  const refreshAfterCompletion = useCallback(
    async (count: number) => {
      const refreshed = await loadImages(true, true);
      if (refreshed) {
        toast.success(
          `Gallery updated with ${count} new image${count === 1 ? "" : "s"}`,
        );
      }
    },
    [loadImages],
  );

  useEffect(() => {
    if (areJobsHydrating) return;

    const completedJobs = jobs.filter(
      (job) => job.status === "completed" || job.status === "partial",
    );
    if (!completionTrackingReadyRef.current) {
      let missingCompletedImages = 0;
      for (const job of completedJobs) {
        seenCompletionsRef.current.add(
          `${job.id}:${job.completed_at ?? job.updated_at}`,
        );
        if (
          normalizeFolder(job.folder_path ?? job.local?.folderPath) === currentFolder
        ) {
          missingCompletedImages += job.outputs.filter(
            (output) =>
              output.status === "ready" &&
              output.asset?.blob_name &&
              !galleryBlobNames.has(output.asset.blob_name),
          ).length;
        }
      }
      completionTrackingReadyRef.current = true;
      if (missingCompletedImages > 0) {
        void refreshAfterCompletion(missingCompletedImages);
      }
      return;
    }

    let completedImages = 0;
    for (const job of completedJobs) {
      const completionKey = `${job.id}:${job.completed_at ?? job.updated_at}`;
      if (seenCompletionsRef.current.has(completionKey)) continue;
      seenCompletionsRef.current.add(completionKey);

      if (
        normalizeFolder(job.folder_path ?? job.local?.folderPath) === currentFolder
      ) {
        completedImages += job.completed_images || job.result?.total_saved || 0;
      }
    }

    if (completedImages > 0) {
      void refreshAfterCompletion(completedImages);
    }
  }, [
    areJobsHydrating,
    currentFolder,
    galleryBlobNames,
    jobs,
    refreshAfterCompletion,
  ]);

  const loadMoreImages = () => {
    if (!hasMore || isLoadingMore) return;
    void loadImages(false);
  };

  return (
    <div className="flex h-full w-full flex-col">
      <PageHeader title={folderPath ? "Album" : "All Images"} />

      <div className="gallery-container h-full w-full flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-3 py-4 pb-40 sm:px-6 sm:py-6 lg:px-8">
          <div className="mb-6 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
            <div className="flex min-w-0 items-center gap-2">
              <p className="text-xs text-muted-foreground">
                {lastRefreshedText}
              </p>
              {folderPath && (
                <Badge variant="outline" className="min-w-0">
                  <FolderIcon className="mr-1 h-3 w-3 shrink-0" />
                  <span className="truncate">
                    {folderPath.split("/").pop() || folderPath}
                  </span>
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      size="icon"
                      variant={autoRefresh ? "outline" : "ghost"}
                      className={autoRefresh ? "relative border-primary text-primary" : "relative text-muted-foreground"}
                      onClick={() => setAutoRefresh((enabled) => !enabled)}
                      aria-pressed={autoRefresh}
                      aria-label={autoRefresh ? "Disable gallery auto-refresh" : "Enable gallery auto-refresh"}
                    >
                      <Clock className="h-4 w-4" />
                      {autoRefresh && (
                        <span className="absolute bottom-1 right-1 h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="left">
                    {autoRefresh ? "Auto-refresh every 30s (on)" : "Auto-refresh every 30s (off)"}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => void loadImages(true, true)}
                disabled={loading || isRefreshing}
                aria-label="Refresh gallery"
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? "motion-safe:animate-spin" : ""}`} />
              </Button>
            </div>
          </div>

          <ImageJobsInline />

          {loading && jobOutputCards.length === 0 ? (
            <GallerySkeletons />
          ) : visibleImages.length > 0 || jobOutputCards.length > 0 ? (
            <div className="w-full">
              <RowBasedMasonryGrid columns={3} gap={4}>
                {jobOutputCards.map(({ job, output }) => (
                  <ImageJobOutputCard
                    key={`${job.id}:${output.index}`}
                    job={job}
                    output={output}
                  />
                ))}
                {visibleImages.map((image, index) => (
                  <ImageGalleryCard
                    key={image.id}
                    image={image}
                    index={jobOutputCards.length + index}
                    onClick={() => setFullscreenImage(image)}
                    onDelete={(deletedImageId) => {
                      offsetRef.current = Math.max(0, offsetRef.current - 1);
                      setImages((current) =>
                        current.filter((item) => item.id !== deletedImageId),
                      );
                    }}
                    onMove={(movedImageId) => {
                      if (folderPath) {
                        offsetRef.current = Math.max(0, offsetRef.current - 1);
                        setImages((current) =>
                          current.filter((item) => item.id !== movedImageId),
                        );
                      } else {
                        void loadImages(true, true);
                      }
                    }}
                  />
                ))}
              </RowBasedMasonryGrid>

              {hasMore && (
                <div className="mt-8 flex justify-center">
                  <Button
                    type="button"
                    onClick={loadMoreImages}
                    disabled={isLoadingMore}
                    variant="outline"
                    className="px-8"
                  >
                    {isLoadingMore ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 motion-safe:animate-spin" />
                        Loading…
                      </>
                    ) : (
                      "Load more images"
                    )}
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex min-h-[40vh] flex-col items-center justify-center py-16 text-center text-muted-foreground">
              <ImageIcon className="mb-4 h-16 w-16 opacity-20" aria-hidden="true" />
              <p className="text-xl">
                {folderPath ? "This album is empty" : "No images yet"}
              </p>
              <p className="mt-2 max-w-md text-sm">
                {folderPath
                  ? `Create an image below to add it to “${folderPath.split("/").pop() || folderPath}”.`
                  : "Describe an image below to start your gallery."}
              </p>
              <Button
                type="button"
                onClick={() => void loadImages(true, true)}
                variant="outline"
                className="mt-6"
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh gallery
              </Button>
            </div>
          )}
        </div>

        <div className="sticky bottom-0 z-20 w-full">
          <ImageCreationContainer
            initialFolder={folderPath || "root"}
            onImagesSaved={(count) => void refreshAfterCompletion(count || 1)}
          />
        </div>
      </div>

      {fullscreenImage && (
        <ImageDetailView
          image={fullscreenImage}
          images={images}
          onClose={() => setFullscreenImage(null)}
          onDelete={(imageId) => {
            offsetRef.current = Math.max(0, offsetRef.current - 1);
            setImages((current) => current.filter((image) => image.id !== imageId));
            setFullscreenImage(null);
          }}
          onMove={(imageId) => {
            if (folderPath) {
              offsetRef.current = Math.max(0, offsetRef.current - 1);
              setImages((current) => current.filter((image) => image.id !== imageId));
              setFullscreenImage(null);
            } else {
              void loadImages(true, true);
            }
          }}
          onNavigate={(_direction, newIndex) => setFullscreenImage(images[newIndex])}
        />
      )}
    </div>
  );
}

export default function NewImagePage() {
  return (
    <PageTransition>
      <Suspense fallback={<div className="p-6">Loading…</div>}>
        <NewImagePageContent />
      </Suspense>
    </PageTransition>
  );
}
