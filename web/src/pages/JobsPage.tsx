import React, { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import PageCallout from "../components/PageCallout";
import StatusBadge from "../components/StatusBadge";
import TechnicalDetails from "../components/TechnicalDetails";
import { humanizeError, jobStatusLabel } from "../lib/errorMessages";

function resultSummary(job: any): string {
  const r = job.result_json;
  if (!r) return "";
  if (r.run_id) return `run_id: ${r.run_id}`;
  if (r.verdict) return `结论: ${r.verdict}`;
  if (r.segment_count != null) return `${r.segment_count} 段, 稳健性 ${r.stability_score}`;
  if (r.exported != null) return `导出 ${r.exported} 只`;
  return "";
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = () => apiGet<any[]>("/api/jobs?limit=50").then(setJobs);
  useEffect(() => {
    load();
  }, []);

  async function retry(jobId: string) {
    setRetrying(jobId);
    try {
      const job = jobs.find((j) => j.id === jobId);
      if (job?.status === "cancelled" && job?.result_json?.checkpoint) {
        await apiPost(`/api/jobs/${jobId}/resume`);
      } else {
        await apiPost(`/api/jobs/${jobId}/retry`);
      }
      await load();
    } finally {
      setRetrying(null);
    }
  }

  return (
    <div>
      <PageCallout>任务记录：人话任务名与状态，便于追溯同步、回测与选股。</PageCallout>
      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="p-2">任务</th>
              <th>状态</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <React.Fragment key={j.id}>
                <tr className="border-t border-slate-800">
                  <td className="p-2">{j.display_name}</td>
                  <td>
                    <StatusBadge
                      ok={j.status === "completed"}
                      label={jobStatusLabel(j.status)}
                    />
                  </td>
                  <td className="text-slate-500">{j.created_at}</td>
                  <td className="space-x-2">
                    <button
                      type="button"
                      className="text-xs text-emerald-400 hover:underline"
                      onClick={() => setExpanded(expanded === j.id ? null : j.id)}
                    >
                      查看
                    </button>
                    {j.status === "failed" && (
                      <button
                        type="button"
                        className="text-xs text-amber-400 hover:underline"
                        disabled={retrying === j.id}
                        onClick={() => retry(j.id)}
                      >
                        重试
                      </button>
                    )}
                    {j.status === "cancelled" && j.result_json?.checkpoint && (
                      <button
                        type="button"
                        className="text-xs text-emerald-400 hover:underline"
                        disabled={retrying === j.id}
                        onClick={() => retry(j.id)}
                      >
                        续传
                      </button>
                    )}
                  </td>
                </tr>
                {expanded === j.id && (
                  <tr className="border-t border-slate-800/50 bg-slate-900/40">
                    <td colSpan={4} className="p-3">
                      {j.status === "failed" && j.error_message && (
                        <p className="mb-2 text-sm text-red-300">{humanizeError(j.error_message).message}</p>
                      )}
                      {resultSummary(j) && (
                        <p className="mb-2 text-sm text-slate-400">{resultSummary(j)}</p>
                      )}
                      <TechnicalDetails data={j.result_json || j.params_json} label="展开完整参数/结果" />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
