import React, { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import PageCallout from "../components/PageCallout";
import JobProgressBar from "../components/JobProgressBar";

export default function DashboardPage() {
  const [status, setStatus] = useState<any>(null);
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [jobStatus, setJobStatus] = useState("");

  const refresh = () => apiGet("/api/status").then(setStatus);
  useEffect(() => {
    refresh();
  }, []);

  const onJob = useCallback(
    (data: Record<string, unknown>) => {
      if (data.job_id === jobId) {
        setProgress(Number(data.progress || 0));
        setJobStatus(String(data.status || ""));
        if (data.status === "completed") refresh();
      }
    },
    [jobId]
  );
  useJobProgress(onJob);

  async function runPipeline() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/pipeline");
    setJobId(res.job_id);
    setProgress(0.05);
    setJobStatus("running");
  }

  return (
    <div>
      <PageCallout>今天建议：{status?.suggestion || "加载中…"}。可一键跑通 ②→③→④。</PageCallout>
      <div className="card">
        <h2 className="mb-3 text-base font-medium">系统状态</h2>
        <p className="text-sm text-slate-400">
          环境检查：{status?.doctor_ok ? "通过" : "待修复"} · 行情覆盖：
          {status?.data_check?.bar_coverage_pct ?? "-"}%
        </p>
        <button className="btn-primary mt-4" onClick={runPipeline}>
          一键跑通
        </button>
        {jobId && <JobProgressBar progress={progress} status={jobStatus} />}
      </div>
      <div className="card mt-4">
        <h2 className="mb-2 text-base font-medium">最近任务</h2>
        <ul className="space-y-1 text-sm text-slate-300">
          {(status?.recent_jobs || []).map((j: any) => (
            <li key={j.id}>
              {j.display_name} — {j.status}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
