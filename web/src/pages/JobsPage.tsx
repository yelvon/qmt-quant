import React, { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../lib/api";
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

const ACTIVE_STATUSES = new Set(["running", "pending"]);

export default function JobsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [cleaning, setCleaning] = useState(false);

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

  async function remove(jobId: string, displayName: string) {
    if (!window.confirm(`确定删除任务「${displayName}」及其报告/回测产物？\n（不会删除已同步的行情数据）`)) {
      return;
    }
    setDeleting(jobId);
    try {
      await apiDelete(`/api/jobs/${jobId}`);
      if (expanded === jobId) setExpanded(null);
      await load();
    } finally {
      setDeleting(null);
    }
  }

  async function cleanupFinished() {
    if (
      !window.confirm(
        "将删除除最近 30 条以外的所有已完成/失败/已取消任务，并清理关联报告与回测记录。\n行情数据不会被删除。",
      )
    ) {
      return;
    }
    setCleaning(true);
    try {
      await apiPost("/api/jobs/cleanup", { keep_last: 30 });
      await load();
    } finally {
      setCleaning(false);
    }
  }

  return (
    <div>
      <PageCallout>任务记录：人话任务名与状态，便于追溯同步、回测与选股。删除任务时会一并清理报告与回测/选股产物，不删除行情库。</PageCallout>
      <div className="mb-3 flex justify-end">
        <button
          type="button"
          className="rounded border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50"
          disabled={cleaning}
          onClick={cleanupFinished}
        >
          {cleaning ? "清理中…" : "清理旧任务（保留最近 30 条）"}
        </button>
      </div>
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
                    {!ACTIVE_STATUSES.has(j.status) && (
                      <button
                        type="button"
                        className="text-xs text-red-400 hover:underline"
                        disabled={deleting === j.id}
                        onClick={() => remove(j.id, j.display_name)}
                      >
                        删除
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
