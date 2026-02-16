"use client"

import { useEffect, useState, useCallback, useRef, Suspense } from "react"
import { listVideoGenerationJobs } from "@/services/api"
import { RefreshCw, Clock } from "lucide-react"
import { PageHeader } from "@/components/page-header"
import { useJobs } from "@/context/jobs-context"
import { VideoJob, convertToVideoJob } from "@/types/jobs"
import { FadeScaleTransition } from "@/components/ui/page-transition"

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { columns } from "./columns"
import { DataTable } from "./data-table"
import { Skeleton } from "@/components/ui/skeleton"

// Content component that may use hooks requiring Suspense
function JobsPageContent() {
  const { setRefreshHandler } = useJobs()
  const [jobs, setJobs] = useState<VideoJob[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isMountedRef = useRef(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  // Stats
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    inProgress: 0,
    completed: 0,
    failed: 0
  })

  const fetchJobs = useCallback(async () => {
    // Don't run fetching if component is not mounted
    if (!isMountedRef.current) return;
    
    // Use setTimeout to ensure state updates happen outside of render phase
    setTimeout(() => {
      if (isMountedRef.current) {
        setLoading(true);
        setError(null);
      }
    }, 0);
    
    try {
      const apiData = await listVideoGenerationJobs(100)
      // Don't update state if component unmounted during fetch
      if (!isMountedRef.current) return;
      
      // Use setTimeout to ensure state updates happen outside of render phase
      setTimeout(() => {
        if (isMountedRef.current) {
          // Convert API data to VideoJob format
          const data = apiData.map(job => convertToVideoJob(job))
          setJobs(data)
          
          // Calculate stats
          const total = data.length
          const pending = data.filter(job => job.status === "pending" || job.status === "queued").length
          const inProgress = data.filter(job => job.status === "in_progress" || job.status === "processing" || job.status === "preprocessing").length
          const completed = data.filter(job => job.status === "completed" || job.status === "succeeded").length
          const failed = data.filter(job => job.status === "failed").length
          
          setStats({
            total,
            pending,
            inProgress,
            completed,
            failed
          })
        }
      }, 0);
    } catch (err) {
      setTimeout(() => {
        if (isMountedRef.current) {
          console.error("Failed to fetch jobs", err)
          setError("Failed to load jobs. Please try again.")
        }
      }, 0);
    } finally {
      setTimeout(() => {
        if (isMountedRef.current) {
          setLoading(false)
        }
      }, 0);
    }
  }, [])

  // Handle auto-refresh toggle
  const toggleAutoRefresh = useCallback(() => {
    setAutoRefresh(prev => !prev);
  }, []);

  // Setup and cleanup interval for auto-refresh
  useEffect(() => {
    // Clear any existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    
    // Setup new interval if auto-refresh is enabled
    if (autoRefresh && isMountedRef.current) {
      console.log("Auto-refresh enabled, setting up 30-second interval");
      intervalRef.current = setInterval(() => {
        if (isMountedRef.current) {
          console.log("Auto-refreshing jobs");
          fetchJobs();
        }
      }, 30000); // 30 seconds
    }
    
    return () => {
      if (intervalRef.current) {
        console.log("Cleaning up auto-refresh interval");
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh, fetchJobs]);

  useEffect(() => {
    // Set mounted flag first
    isMountedRef.current = true;
    
    // Create a dedicated refresh function that only runs if component is mounted
    const refreshFunction = async () => {
      console.log("Refresh function called from refresh handler");
      if (isMountedRef.current) {
        return fetchJobs();
      }
      return Promise.resolve();
    };
    
    // Register the refresh handler
    console.log("Jobs page: Registering refresh handler");
    setRefreshHandler(refreshFunction);
    
    // Initial fetch - run after a small delay to avoid render-phase updates
    const initialFetchTimeout = setTimeout(() => {
      if (isMountedRef.current) {
        fetchJobs();
      }
    }, 10);
    
    return () => {
      console.log("Jobs page: Cleaning up and removing refresh handler");
      isMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      clearTimeout(initialFetchTimeout);
      setRefreshHandler(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Dependency array intentionally empty to avoid resetting handler on re-renders

  return (
    <div className="flex flex-col h-full w-full">
      <PageHeader title="Video Generation Jobs" />
      
      <div className="flex-1 w-full h-full overflow-y-auto">
        <div className="w-full mx-auto px-10 py-6 pb-16">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4 mb-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-2xl">{stats.total}</CardTitle>
                <CardDescription>Total Jobs</CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-2xl">{stats.pending + stats.inProgress}</CardTitle>
                <CardDescription>In Queue</CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-2xl">{stats.completed}</CardTitle>
                <CardDescription>Completed</CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-2xl">{stats.failed}</CardTitle>
                <CardDescription>Failed</CardDescription>
              </CardHeader>
            </Card>
          </div>

          {error && (
            <div className="rounded-md bg-destructive/15 p-4 text-destructive mb-6">
              {error}
            </div>
          )}

          <div className="mb-4 flex justify-between items-center">
            <h2 className="text-xl font-semibold">Recent Jobs</h2>
            <div className="flex items-center space-x-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={toggleAutoRefresh}
                      className="flex items-center space-x-1"
                    >
                      {autoRefresh ? (
                        <>
                          <Clock className="h-4 w-4 mr-2" />
                          <span>Auto-refreshing</span>
                        </>
                      ) : (
                        <>
                          <RefreshCw className="h-4 w-4 mr-2" />
                          <span>Refresh</span>
                        </>
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">
                    <p>{autoRefresh ? "Turn off auto-refresh" : "Turn on auto-refresh (30 seconds)"}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
          
          <DataTable
            columns={columns}
            data={jobs}
            isLoading={loading}
          />
        </div>
      </div>
    </div>
  )
}

// Main component with Suspense boundary
export default function JobsPage() {
  return (
    <FadeScaleTransition>
      <Suspense fallback={
        <div className="flex flex-col h-full w-full">
          <PageHeader title="Video Generation Jobs" />
          <div className="flex-1 w-full h-full overflow-y-auto">
            <div className="w-full mx-auto px-10 py-6 pb-16">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-4 mb-6">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Card key={i}>
                    <CardHeader className="pb-2">
                      <Skeleton className="h-8 w-16" />
                      <Skeleton className="h-4 w-24" />
                    </CardHeader>
                  </Card>
                ))}
              </div>
              
              <div className="mb-4 flex justify-between items-center">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-8 w-24" />
              </div>
              
              <div className="rounded-md border">
                <div className="p-4">
                  <Skeleton className="h-[400px] w-full" />
                </div>
              </div>
            </div>
          </div>
        </div>
      }>
        <JobsPageContent />
      </Suspense>
    </FadeScaleTransition>
  )
} 