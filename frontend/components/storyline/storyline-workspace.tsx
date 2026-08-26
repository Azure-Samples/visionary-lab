"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import {
  AlertCircle,
  Layers3,
  Loader2,
  Plus,
  RefreshCw,
} from "lucide-react";
import { StorylineComposer } from "@/components/storyline/storyline-composer";
import { StorylineDetail } from "@/components/storyline/storyline-detail";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  cancelStoryline,
  getStoryline,
  listStorylines,
  regenerateStorylineFrame,
  retryStorylineFrame,
  retryStorylinePlanning,
  startStoryline,
  updateStorylinePlan,
} from "@/services/storylines";
import type { Storyline, StorylinePlan } from "@/types/storyline";
import { cn } from "@/utils/cn";

function upsertStoryline(items: Storyline[], storyline: Storyline): Storyline[] {
  return [
    storyline,
    ...items.filter((item) => item.id !== storyline.id),
  ].sort(
    (a, b) =>
      (Date.parse(b.updated_at) || 0) - (Date.parse(a.updated_at) || 0),
  );
}

function statusTone(status: Storyline["status"]): string {
  if (status === "completed") return "text-emerald-600";
  if (status === "partial") return "text-amber-600";
  if (status === "failed") return "text-destructive";
  return "text-muted-foreground";
}

function shouldPollStoryline(status: Storyline["status"]): boolean {
  return ["queued", "generating", "cancel_requested"].includes(status);
}

export function StorylineWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedId = searchParams.get("storyline");
  const [items, setItems] = useState<Storyline[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(requestedId);
  const [selected, setSelected] = useState<Storyline | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isRefreshingDetail, setIsRefreshingDetail] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const detailRequestSequenceRef = useRef(0);
  const selectedStatus = selected?.status;

  useEffect(() => {
    setSelectedId(requestedId);
    setSelected((current) =>
      current && current.id === requestedId ? current : null,
    );
  }, [requestedId]);

  const selectStoryline = useCallback(
    (storylineId: string) => {
      detailRequestSequenceRef.current += 1;
      setSelectedId(storylineId);
      setSelected((current) =>
        current?.id === storylineId ? current : null,
      );
      const params = new URLSearchParams(searchParams.toString());
      params.set("mode", "storyline");
      params.set("storyline", storylineId);
      router.replace(`/new-image?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  const loadList = useCallback(async () => {
    setIsLoadingList(true);
    try {
      const response = await listStorylines({ limit: 50 });
      setItems(response.items);
      setListError(null);
      if (!selectedId && response.items.length > 0) {
        selectStoryline(response.items[0].id);
      }
    } catch (error) {
      setListError(
        error instanceof Error ? error.message : "Could not load storylines",
      );
    } finally {
      setIsLoadingList(false);
    }
  }, [selectStoryline, selectedId]);

  const loadDetail = useCallback(
    async (background = false) => {
      if (!selectedId) {
        detailRequestSequenceRef.current += 1;
        setSelected(null);
        return;
      }
      const requestSequence = ++detailRequestSequenceRef.current;
      if (!background) setIsRefreshingDetail(true);
      try {
        const storyline = await getStoryline(selectedId);
        if (requestSequence !== detailRequestSequenceRef.current) return;
        setSelected(storyline);
        setItems((current) => upsertStoryline(current, storyline));
        setListError(null);
      } catch (error) {
        if (!background && requestSequence === detailRequestSequenceRef.current) {
          setListError(
            error instanceof Error ? error.message : "Could not load storyline",
          );
        }
      } finally {
        if (!background && requestSequence === detailRequestSequenceRef.current) {
          setIsRefreshingDetail(false);
        }
      }
    },
    [selectedId],
  );

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    if (!selectedStatus || !shouldPollStoryline(selectedStatus)) return;
    const intervalId = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadDetail(true);
    }, 3_000);
    return () => window.clearInterval(intervalId);
  }, [loadDetail, selectedStatus]);

  const selectedFromList = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  );
  const displayed = selected ?? selectedFromList;

  const applyMutationResult = (storyline: Storyline) => {
    detailRequestSequenceRef.current += 1;
    setSelected(storyline);
    setItems((current) => upsertStoryline(current, storyline));
  };

  return (
    <div className="flex h-full w-full flex-col">
      <PageHeader
        title="Storyline"
        description="Consistent multi-image campaigns, ordered frame by frame"
      />
      <div className="h-full flex-1 overflow-y-auto">
        <div className="mx-auto grid w-full max-w-[110rem] items-start gap-6 px-3 py-5 pb-16 sm:px-6 lg:px-8 xl:grid-cols-[25rem_minmax(0,1fr)]">
          <aside className="space-y-5">
            <StorylineComposer
              onCreated={(storyline) => {
                setItems((current) => upsertStoryline(current, storyline));
                setSelected(storyline);
                selectStoryline(storyline.id);
              }}
            />

            <Card className="gap-3 border-border/70 shadow-sm">
              <CardHeader className="pb-0">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">Your storylines</CardTitle>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Reopen plans and generated model lanes.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => void loadList()}
                    disabled={isLoadingList}
                    aria-label="Refresh storyline list"
                  >
                    <RefreshCw
                      className={cn(
                        "size-4",
                        isLoadingList && "motion-safe:animate-spin",
                      )}
                    />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="px-3">
                {isLoadingList && items.length === 0 ? (
                  <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
                    <Loader2 className="size-4 motion-safe:animate-spin" />
                    Loading storylines…
                  </div>
                ) : items.length === 0 ? (
                  <div className="flex flex-col items-center py-8 text-center">
                    <div className="flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                      <Layers3 className="size-5" />
                    </div>
                    <p className="mt-3 text-sm font-medium">No storylines yet</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Create your first ordered campaign above.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {items.map((storyline) => {
                      const active = storyline.id === selectedId;
                      return (
                        <button
                          key={storyline.id}
                          type="button"
                          className={cn(
                            "w-full rounded-lg border border-transparent px-3 py-2.5 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                            active && "border-primary/20 bg-primary/5",
                          )}
                          onClick={() => selectStoryline(storyline.id)}
                          aria-current={active ? "page" : undefined}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="line-clamp-1 text-sm font-medium">
                              {storyline.title}
                            </span>
                            <Badge variant="outline" className="shrink-0 text-[9px] capitalize">
                              {storyline.status.replaceAll("_", " ")}
                            </Badge>
                          </div>
                          <div className="mt-1.5 flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
                            <span>
                              {storyline.settings.frame_count} frames ·{" "}
                              {storyline.settings.models.length} model
                              {storyline.settings.models.length === 1 ? "" : "s"}
                            </span>
                            <span className={statusTone(storyline.status)}>
                              {formatDistanceToNow(new Date(storyline.updated_at), {
                                addSuffix: true,
                              })}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </aside>

          <main className="min-w-0">
            {listError && (
              <Alert variant="destructive" className="mb-5">
                <AlertCircle />
                <AlertTitle>Storyline service unavailable</AlertTitle>
                <AlertDescription>{listError}</AlertDescription>
              </Alert>
            )}

            {displayed ? (
              <StorylineDetail
                key={displayed.id}
                storyline={displayed}
                isRefreshing={isRefreshingDetail}
                onRefresh={() => loadDetail()}
                onCancel={async () => {
                  const updated = await cancelStoryline(displayed);
                  applyMutationResult(updated);
                }}
                onStart={async () => {
                  const updated = await startStoryline(displayed);
                  applyMutationResult(updated);
                }}
                onRetryPlanning={async () => {
                  const updated = await retryStorylinePlanning(displayed);
                  applyMutationResult(updated);
                }}
                onRetryFrame={async (frameId) => {
                  const updated = await retryStorylineFrame(displayed, frameId);
                  applyMutationResult(updated);
                }}
                onRegenerateFrame={async (frameId, overrides) => {
                  const updated = await regenerateStorylineFrame(
                    displayed,
                    frameId,
                    overrides,
                  );
                  applyMutationResult(updated);
                }}
                onSavePlan={async (plan: StorylinePlan) => {
                  const updated = await updateStorylinePlan(displayed, plan);
                  applyMutationResult(updated);
                }}
              />
            ) : (
              <Card className="border-dashed shadow-none">
                <CardContent className="flex min-h-[32rem] flex-col items-center justify-center p-8 text-center">
                  <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Plus className="size-7" />
                  </div>
                  <h2 className="mt-5 text-lg font-semibold">Create a connected image story</h2>
                  <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">
                    Start with text or reference images, compare model lanes, and keep every
                    frame aligned to one shared visual direction.
                  </p>
                </CardContent>
              </Card>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
