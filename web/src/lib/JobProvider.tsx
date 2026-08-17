import React from "react";
import { Link } from "react-router-dom";
import { apiGet } from "./api";
import { inferJobTypeFromMessage, jobRouteForType, jobTypeLabel } from "./jobTypes";
import { formatEtaSeconds, humanizeProgressMessage } from "./jobProgressUi";

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
  result: Record<string, unknown> | null;
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
  result: null,
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
  if (TERMINAL.has(prev.status) && status === "running") {
    return prev;
  }
  const resultPayload = data.result as Record<string, unknown> | undefined;
  const checkpoint = resultPayload?.checkpoint;
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
    result: resultPayload ?? prev.result,
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
    result: (result as Record<string, unknown> | undefined) ?? null,
  };
}

const TRACKED_JOB_KEY = "qmt_tracked_job_id";

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
        result: null,
      });
      try {
        sessionStorage.setItem(TRACKED_JOB_KEY, jobId);
      } catch {
        /* ignore */
      }
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
          return;
        }
        let savedId = "";
        try {
          savedId = sessionStorage.getItem(TRACKED_JOB_KEY) || "";
        } catch {
          savedId = "";
        }
        if (!savedId) return;
        const saved = jobs.find((j) => String(j.id || "") === savedId);
        if (saved && String(saved.status || "") === "completed") {
          adoptJob(saved);
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
    if (!id) return;

    let cancelled = false;

    const pull = async () => {
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

    if (TERMINAL.has(state.status)) {
      if (state.status === "completed" && !state.result) {
        pull();
        const timer = window.setInterval(() => {
          if (cancelled) return;
          pull();
        }, 1200);
        const stop = window.setTimeout(() => {
          window.clearInterval(timer);
        }, 15000);
        return () => {
          cancelled = true;
          window.clearInterval(timer);
          window.clearTimeout(stop);
        };
      }
      return () => {
        cancelled = true;
      };
    }

    const intervalMs = state.cancelling ? 800 : 2000;
    pull();
    const timer = window.setInterval(pull, intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [state.jobId, state.status, state.cancelling, state.result, handleUpdate]);

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
  const [others, setOthers] = React.useState<Record<string, unknown>[]>([]);

  const refreshOthers = React.useCallback(() => {
    apiGet<Record<string, unknown>[]>("/api/jobs?limit=30")
      .then((jobs) => {
        const running = jobs.filter((j) => {
          const status = String(j.status || "");
          return status === "running" || status === "pending";
        });
        setOthers(running);
      })
      .catch(() => {
        /* ignore */
      });
  }, []);

  React.useEffect(() => {
    refreshOthers();
    const timer = window.setInterval(refreshOthers, 4000);
    return () => window.clearInterval(timer);
  }, [refreshOthers, job.status, job.jobId]);

  const focusedVisible =
    Boolean(job.jobId) &&
    (job.isRunning || job.status === "cancelled" || job.status === "completed" || job.status === "failed");
  const extra = others.filter((j) => String(j.id || "") !== job.jobId);
  if (!focusedVisible && extra.length === 0) return null;

  const pct = Math.round(Math.min(1, Math.max(0, job.progress)) * 100);
  const typeLabel = jobTypeLabel(job.jobType || inferJobTypeFromMessage(job.message));
  const dataRoute = jobRouteForType(job.jobType || inferJobTypeFromMessage(job.message));
  const etaLabel = formatEtaSeconds(job.etaSeconds);

  return (
    <div className="border-b border-emerald-900/40 bg-emerald-950/40 px-4 py-2 sm:px-6">
      <div className="mx-auto max-w-6xl space-y-1">
        {focusedVisible && (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Link to={dataRoute} className="shrink-0 text-emerald-400 hover:underline">
                {typeLabel}
                {job.status === "completed"
                  ? "已完成"
                  : job.status === "failed"
                    ? "失败"
                    : job.status === "cancelled"
                      ? "已中断"
                      : "进行中"}
              </Link>
              <span className="min-w-0 flex-1 truncate text-slate-300">
                {humanizeProgressMessage(job.message) || "运行中…"}
              </span>
              {job.isRunning && <span className="shrink-0 text-slate-400">{pct}%</span>}
              {job.isRunning && (
                <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-800 sm:w-32">
                  <div className="h-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
                </div>
              )}
              {job.status === "completed" && (
                <Link to={dataRoute} className="shrink-0 text-xs text-emerald-300 underline">
                  查看结果
                </Link>
              )}
              {!job.isRunning && (
                <button type="button" className="shrink-0 text-xs text-slate-500 hover:text-slate-300" onClick={job.resetJob}>
                  关闭
                </button>
              )}
            </div>
            {(job.detail || etaLabel) && (
              <p className="truncate pl-0 text-xs text-slate-500">
                {job.detail}
                {job.detail && etaLabel ? " · " : ""}
                {etaLabel ? `预计剩余 ${etaLabel}` : ""}
              </p>
            )}
          </>
        )}
        {extra.map((j) => {
          const jType = String(j.job_type || "");
          const jRoute = jobRouteForType(jType);
          const jLabel = jobTypeLabel(jType);
          return (
            <div key={String(j.id)} className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
              <Link to={jRoute} className="text-emerald-500 hover:underline">
                另有{jLabel}进行中
              </Link>
              <span className="truncate">{String(j.progress_message || j.display_name || "")}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
