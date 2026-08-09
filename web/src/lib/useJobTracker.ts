import React from "react";

export type JobState = {
  jobId: string;
  progress: number;
  status: string;
  message: string;
  error: string | null;
  canResume: boolean;
  cancelling: boolean;
  etaSeconds: number | null;
};

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

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
    progress: Number(data.progress ?? prev.progress ?? 0),
    status,
    message: String(data.message || data.progress_message || prev.message || ""),
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

export function useJobTracker() {
  const [state, setState] = React.useState<JobState>({
    jobId: "",
    progress: 0,
    status: "",
    message: "",
    error: null,
    canResume: false,
    cancelling: false,
    etaSeconds: null,
  });
  const jobIdRef = React.useRef("");

  const handleUpdate = React.useCallback((data: Record<string, unknown>) => {
    const id = jobIdRef.current;
    if (!id) return;
    setState((prev) => applyJobPayload(prev, data, id));
  }, []);

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

  const trackJob = React.useCallback((jobId: string, message = "任务已提交…") => {
    jobIdRef.current = jobId;
    setState({
      jobId,
      progress: 0.05,
      status: "running",
      message,
      error: null,
      canResume: false,
      cancelling: false,
      etaSeconds: null,
    });
  }, []);

  const resetJob = React.useCallback(() => {
    jobIdRef.current = "";
    setState({
      jobId: "",
      progress: 0,
      status: "",
      message: "",
      error: null,
      canResume: false,
      cancelling: false,
      etaSeconds: null,
    });
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
      message: "正在中断，等待当前股票下载结束…",
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
    trackJob(data.job_id, "续传同步中…");
  }, [trackJob]);

  const isRunning = state.status === "running" || state.status === "pending";

  return {
    ...state,
    isRunning,
    trackJob,
    resetJob,
    cancelJob,
    resumeJob,
  };
}
