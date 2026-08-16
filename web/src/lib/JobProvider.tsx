import React from "react";
import { Link } from "react-router-dom";
import { apiGet } from "./api";
import { inferJobTypeFromMessage, jobRouteForType, jobTypeLabel } from "./jobTypes";
import { formatEtaSeconds } from "./jobProgressUi";

export type JobState = {
  jobId: string;
  jobType: string;
  progress: number;
  status: string;
  message: string;
  detail: string;
  step: string;
  error: string | null;
  canResume: boolean;
  cancelling: boolean;
  etaSeconds: number | null;
};

export type JobTrackerValue = JobState & {
  isRunning: boolean;
  trackJob: (jobId: string, message?: string, jobType?: string) => void;
  resetJob: () => void;
  cancelJob: () => Promise<boolean>;
  resumeJob: () => Promise<void>;
};

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

const EMPTY_STATE: JobState = {
  jobId: "",
  jobType: "",
  progress: 0,
  status: "",
  message: "",
  detail: "",
  step: "",
  error: null,
  canResume: false,
  cancelling: false,
  etaSeconds: null,
};

const JobContext = React.createContext<JobTrackerValue | null>(null);

function resolveJobType(data: Record<string, unknown>, prev: JobState): string {
  const explicit = String(data.job_type || "");
  if (explicit) return explicit;
  const message = String(data.message || data.progress_message || prev.message || "");
  return inferJobTypeFromMessage(message) || prev.jobType;
}

function applyJobPayload(
  prev: JobState,
  data: Record<string, unknown>,
  jobId: string
): JobState {
  if (data.job_id && data.job_id !== jobId) return prev;
  const status = String(data.status || prev.status || "");
  const result = (data.result as Record<string, unknown> | undefined) || undefined;
  const checkpoint = result?.checkpoint;
  const cancelling =
    Boolean(data.cancelling) || (prev.cancelling && status === "running");
  return {
    jobId,
    jobType: resolveJobType(data, prev),
    progress: Number(data.progress ?? prev.progress ?? 0),
    status,
    message: String(data.message || data.progress_message || prev.message || ""),
    detail: String(data.detail ?? prev.detail ?? ""),
    step: String(data.step ?? prev.step ?? ""),
    error: data.error ? String(data.error) : status === "failed" ? prev.error : null,
    canResume: status === "cancelled" && !!checkpoint,
    cancelling: status === "cancelled" ? false : cancelling,
    etaSeconds:
      data.eta_seconds != null
        ? Number(data.eta_seconds)
        : status === "running"
          ? prev.etaSeconds
          : null,
  };
}

function stateFromApiJob(job: Record<string, unknown>): JobState {
  const status = String(job.status || "");
  const result = job.result_json as Record<string, unknown> | undefined;
  const message = String(job.progress_message || job.display_name || "");
  return {
    jobId: String(job.id || ""),
    jobType: String(job.job_type || inferJobTypeFromMessage(message) || ""),
    progress: Number(job.progress ?? 0.05),
    status,
    message,
    detail: "",
    step: "",
    error: job.error_message ? String(job.error_message) : null,
    canResume: status === "cancelled" && !!result?.checkpoint,
    cancelling: Boolean(job.cancel_requested),
    etaSeconds: null,
  };
}

export function JobProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<JobState>(EMPTY_STATE);
  const jobIdRef = React.useRef("");
  const jobTypeRef = React.useRef("");
  const restoredRef = React.useRef(false);

  const handleUpdate = React.useCallback((data: Record<string, unknown>) => {
    const id = jobIdRef.current;
    if (!id) return;
    setState((prev) => applyJobPayload(prev, data, id));
  }, []);

  const trackJob = React.useCallback(
    (jobId: string, message = "任务已提交…", jobType = "") => {
      jobIdRef.current = jobId;
      jobTypeRef.current = jobType || inferJobTypeFromMessage(message);
      setState({
        jobId,
        jobType: jobTypeRef.current,
        progress: 0.05,
        status: "running",
        message,
        detail: "",
        step: "",
        error: null,
        canResume: false,
        cancelling: false,
        etaSeconds: null,
      });
    },
    []
  );

  const adoptJob = React.useCallback((job: Record<string, unknown>) => {
    const next = stateFromApiJob(job);
    if (!next.jobId) return;
    jobIdRef.current = next.jobId;
    jobTypeRef.current = next.jobType;
    setState(next);
  }, []);

  React.useEffect(() => {
    if (restoredRef.current) return;
    restoredRef.current = true;

    apiGet<Record<string, unknown>[]>("/api/jobs?limit=30")
      .then((jobs) => {
        if (jobIdRef.current) return;
        const active = jobs.find((j) => {
          const status = String(j.status || "");
          return status === "running" || status === "pending";
        });
        if (active) {
          adoptJob(active);
        }
      })
      .catch(() => {
        /* ignore */
      });
  }, [adoptJob]);

  React.useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/jobs`);
    ws.onmessage = (ev) => {
      try {
        handleUpdate(JSON.parse(ev.data));
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, [handleUpdate]);

  React.useEffect(() => {
    const id = state.jobId;
    if (!id || TERMINAL.has(state.status)) return;

    let cancelled = false;
    const intervalMs = state.cancelling ? 800 : 2000;
    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${id}`);
        if (!res.ok || cancelled) return;
        const job = await res.json();
        handleUpdate({
          job_id: id,
          job_type: job.job_type,
          status: job.status,
          progress: job.progress,
          message: job.progress_message,
          error: job.error_message,
          result: job.result_json,
          cancelling: job.cancel_requested,
        });
      } catch {
        /* ignore */
      }
    };
    poll();
    const timer = window.setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [state.jobId, state.status, state.cancelling, handleUpdate]);

  const resetJob = React.useCallback(() => {
    jobIdRef.current = "";
    jobTypeRef.current = "";
    setState(EMPTY_STATE);
  }, []);

  const cancelJob = React.useCallback(async () => {
    const id = jobIdRef.current;
    if (!id) return false;
    const res = await fetch(`/api/jobs/${id}/cancel`, { method: "POST" });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "中断失败");
    }
    setState((prev) => ({
      ...prev,
      cancelling: true,
      message: "正在中断，等待当前批次结束…",
    }));
    return true;
  }, []);

  const resumeJob = React.useCallback(async () => {
    const id = jobIdRef.current;
    if (!id) return;
    const res = await fetch(`/api/jobs/${id}/resume`, { method: "POST" });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "续传失败");
    }
    const data = await res.json();
    trackJob(data.job_id, "续传同步中…", jobTypeRef.current);
  }, [trackJob]);

  const isRunning = state.status === "running" || state.status === "pending";

  const value = React.useMemo<JobTrackerValue>(
    () => ({
      ...state,
      isRunning,
      trackJob,
      resetJob,
      cancelJob,
      resumeJob,
    }),
    [state, isRunning, trackJob, resetJob, cancelJob, resumeJob]
  );

  return <JobContext.Provider value={value}>{children}</JobContext.Provider>;
}

export function useJobTracker(): JobTrackerValue {
  const ctx = React.useContext(JobContext);
  if (!ctx) {
    throw new Error("useJobTracker must be used within JobProvider");
  }
  return ctx;
}

/** Compact banner shown in Layout while a job is active. */
export function GlobalJobBanner() {
  const job = useJobTracker();
  if (!job.jobId) return null;
  if (!job.isRunning && job.status !== "cancelled") return null;

  const pct = Math.round(Math.min(1, Math.max(0, job.progress)) * 100);
  const typeLabel = jobTypeLabel(job.jobType || inferJobTypeFromMessage(job.message));
  const dataRoute = jobRouteForType(job.jobType || inferJobTypeFromMessage(job.message));
  const etaLabel = formatEtaSeconds(job.etaSeconds);

  return (
    <div className="border-b border-emerald-900/40 bg-emerald-950/40 px-6 py-2">
      <div className="mx-auto max-w-6xl space-y-1">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Link to={dataRoute} className="shrink-0 text-emerald-400 hover:underline">
            {typeLabel}进行中
          </Link>
          <span className="min-w-0 flex-1 truncate text-slate-300">{job.message || "运行中…"}</span>
          <span className="shrink-0 text-slate-400">{pct}%</span>
          <div className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-800">
            <div className="h-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>
        {(job.detail || etaLabel) && (
          <p className="truncate pl-0 text-xs text-slate-500">
            {job.detail}
            {job.detail && etaLabel ? " · " : ""}
            {etaLabel ? `预计剩余 ${etaLabel}` : ""}
          </p>
        )}
      </div>
    </div>
  );
}
