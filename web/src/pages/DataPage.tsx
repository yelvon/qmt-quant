import React, { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";

export default function DataPage() {
  const [sector, setSector] = useState("沪深A股");
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [check, setCheck] = useState<any>(null);
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");

  useEffect(() => {
    apiGet<any[]>("/api/options/sectors").then(setSectors);
    apiGet("/api/data/check").then(setCheck);
  }, []);

  const onJob = useCallback(
    (data: Record<string, unknown>) => {
      if (data.job_id === jobId) {
        setProgress(Number(data.progress || 0));
        setStatus(String(data.status || ""));
        if (data.status === "completed") apiGet("/api/data/check").then(setCheck);
      }
    },
    [jobId]
  );
  useJobProgress(onJob);

  async function syncBars() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/sync/bars", {
      sector,
      incremental: true,
      days: 5,
    });
    setJobId(res.job_id);
  }

  async function syncFinancial() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/sync/financial", { sector });
    setJobId(res.job_id);
  }

  async function exportCatalog() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/catalog/export");
    setJobId(res.job_id);
  }

  return (
    <div>
      <PageCallout>仅下拉/勾选，Primary =「更新今日数据」。同步完成后可导出 Parquet 供验策略使用。</PageCallout>
      <div className="card grid gap-4 md:grid-cols-2">
        <PresetSelect label="股票池" value={sector} options={sectors} onChange={setSector} />
        <div className="flex items-end gap-2">
          <button className="btn-primary" onClick={syncBars}>
            更新今日数据
          </button>
          <button className="btn-secondary" onClick={syncFinancial}>
            同步财报
          </button>
          <button className="btn-secondary" onClick={exportCatalog}>
            导出验策略文件
          </button>
        </div>
        {jobId && <JobProgressBar progress={progress} status={status} />}
      </div>
      <div className="card mt-4">
        <h2 className="mb-2 font-medium">数据健康</h2>
        <pre className="overflow-auto text-xs text-slate-400">{JSON.stringify(check, null, 2)}</pre>
      </div>
    </div>
  );
}
