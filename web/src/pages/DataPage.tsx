import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import DataHealthPanel from "../components/DataHealthPanel";

const ADJUST_OPTIONS = [
  { id: "front", label: "前复权" },
  { id: "none", label: "不复权" },
  { id: "back", label: "后复权" },
];

const RANGE_OPTIONS = [
  { id: "", label: "增量（近5日）" },
  { id: "1y", label: "全量 1 年" },
  { id: "3y", label: "全量 3 年" },
  { id: "5y", label: "全量 5 年" },
];

export default function DataPage() {
  const [sector, setSector] = useState("沪深A股");
  const [adjust, setAdjust] = useState("front");
  const [rangePreset, setRangePreset] = useState("");
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [check, setCheck] = useState<any>(null);
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const [jobError, setJobError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<any[]>("/api/options/sectors").then(setSectors);
    apiGet("/api/data/check").then(setCheck);
  }, []);

  const onJob = useCallback(
    (data: Record<string, unknown>) => {
      if (data.job_id === jobId) {
        setProgress(Number(data.progress || 0));
        setStatus(String(data.status || ""));
        if (data.error) setJobError(String(data.error));
        if (data.status === "completed") {
          apiGet("/api/data/check").then(setCheck);
          setJobError(null);
        }
      }
    },
    [jobId]
  );
  useJobProgress(onJob);

  async function syncBars(incremental: boolean) {
    const res = await apiPost<{ job_id: string }>("/api/jobs/sync/bars", {
      sector,
      incremental,
      days: 5,
      adjust,
      range_preset: incremental ? undefined : rangePreset || undefined,
    });
    setJobId(res.job_id);
    setJobError(null);
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
      <p className="mb-4 text-sm text-slate-400">
        <Link to="/data/browse" className="text-emerald-400 hover:underline">
          查看已同步数据 →
        </Link>
      </p>
      <div className="card grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <PresetSelect label="股票池" value={sector} options={sectors} onChange={setSector} />
        <PresetSelect label="复权" value={adjust} options={ADJUST_OPTIONS} onChange={setAdjust} />
        <PresetSelect label="历史长度" value={rangePreset} options={RANGE_OPTIONS} onChange={setRangePreset} />
        <div className="flex flex-wrap items-end gap-2 lg:col-span-3">
          <button className="btn-primary" onClick={() => syncBars(true)}>
            更新今日数据
          </button>
          <button className="btn-secondary" onClick={() => syncBars(false)}>
            全量同步
          </button>
          <button className="btn-secondary" onClick={syncFinancial}>
            同步财报
          </button>
          <button className="btn-secondary" onClick={exportCatalog}>
            导出验策略文件
          </button>
        </div>
        {jobId && (
          <JobProgressBar
            progress={progress}
            status={status}
            error={jobError}
            completeAction={status === "completed" ? { label: "去试策略", to: "/research" } : undefined}
          />
        )}
      </div>
      <div className="card mt-4">
        <h2 className="mb-3 font-medium">数据健康</h2>
        <DataHealthPanel check={check} />
      </div>
    </div>
  );
}
