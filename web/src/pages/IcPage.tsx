import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { fetchJobRecord, resultFromJobRecord } from "../lib/jobResult";
import { isIcJob } from "../lib/jobTypes";
import { useJobTracker } from "../lib/useJobTracker";
import { parseApiError } from "../lib/errorMessages";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import TechnicalDetails from "../components/TechnicalDetails";
import EmptyState from "../components/EmptyState";

export default function IcPage() {
  const [params] = useSearchParams();
  const job = useJobTracker();
  const icActive = Boolean(job.jobId) && isIcJob(job.jobType);

  const [template, setTemplate] = useState(params.get("template") || "low_pe");
  const [sector, setSector] = useState(params.get("sector") || "沪深A股");
  const [templates, setTemplates] = useState<{ id: string; label: string }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [result, setResult] = useState<any>(null);
  const [frequency, setFrequency] = useState("daily");
  const [horizons, setHorizons] = useState("5,20");
  const [pageError, setPageError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiGet<any[]>("/api/options/templates").then(setTemplates);
    apiGet<any[]>("/api/options/sectors").then(setSectors);
  }, []);

  useEffect(() => {
    if (!icActive || !job.jobId || job.status !== "completed") return;
    let cancelled = false;
    (async () => {
      try {
        const record = await fetchJobRecord(job.jobId);
        const payload = resultFromJobRecord(record);
        if (!payload || cancelled) return;
        setResult(payload);
      } catch (err) {
        if (!cancelled) setPageError(parseApiError(err instanceof Error ? err.message : String(err)));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [icActive, job.jobId, job.status]);

  async function runIc() {
    const parsedHorizons = horizons.split(/[,，\s]+/).map(Number).filter((v) => Number.isInteger(v) && v > 0);
    if (!parsedHorizons.length) {
      setPageError("请输入至少一个正整数收益周期，例如 5,20");
      return;
    }
    setSubmitting(true);
    setPageError(null);
    try {
      const res = await apiPost<{ job_id: string }>("/api/jobs/screen/ic", {
        template, sector, frequency, horizons: parsedHorizons,
      });
      setResult(null);
      job.trackJob(res.job_id, "因子 IC 计算中…", "screen_ic");
    } catch (err) {
      setPageError(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setSubmitting(false);
    }
  }

  const factorSource = result?.factors || result?.ic || {};
  const icRows = Object.entries(factorSource as Record<string, any>).flatMap(([factor, value]) => {
    if (!value?.horizons) return [[factor, "", value] as const];
    return Object.entries(value.horizons as Record<string, any>).map(([horizon, stats]) => [factor, horizon, stats] as const);
  });

  return (
    <div>
      <PageCallout>
        因子 IC：衡量选股因子与未来收益的相关性。|IC| &gt; 0.03 通常认为因子较有效。
      </PageCallout>
      <div className="card grid gap-3 md:grid-cols-2">
        <PresetSelect label="模板" value={template} options={templates} onChange={setTemplate} />
        <PresetSelect label="范围" value={sector} options={sectors} onChange={setSector} />
        <PresetSelect label="计算频率" value={frequency} options={[{ id: "daily", label: "日线" }, { id: "weekly", label: "周线" }]} onChange={setFrequency} />
        <label>
          <span className="label">未来收益周期</span>
          <input className="input w-full" value={horizons} onChange={(e) => setHorizons(e.target.value)} placeholder="5,20" />
          <span className="mt-1 block text-xs text-slate-500">逗号分隔，单位为{frequency === "weekly" ? "周" : "交易日"}</span>
        </label>
      </div>
      <button className="btn-primary mt-4" disabled={job.isRunning || submitting} onClick={runIc}>
        {submitting ? "提交中…" : "计算 IC"}
      </button>
      {pageError && <p className="mt-3 text-sm text-red-300">{pageError}</p>}
      {icActive && (
        <JobProgressBar
          progress={job.progress}
          status={job.status}
          message={job.message}
          error={job.error}
          jobType={job.jobType}
          step={job.step}
          detail={job.detail}
          etaSeconds={job.etaSeconds}
        />
      )}
      {!result && !icActive && (
        <EmptyState title="还没有 IC 结果" description="选择模板与范围后点击「计算 IC」。" />
      )}
      {icRows.length > 0 && (
        <div className="card mt-4 overflow-x-auto">
          <h2 className="mb-2 font-medium">IC 结果</h2>
          <p className="mb-3 text-sm text-slate-400">样本池 {result.universe_size} 只</p>
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="p-2">因子</th>
                <th>周期</th>
                <th>IC 均值</th>
                <th>IC 标准差</th>
                <th>ICIR</th>
                <th>日期数</th>
                <th>样本数</th>
                <th>评价</th>
              </tr>
            </thead>
            <tbody>
              {icRows.map(([factor, horizon, stats]) => {
                const ic = Math.abs(stats.ic_mean ?? 0);
                const good = ic >= 0.03;
                return (
                  <tr key={`${factor}-${horizon}`} className="border-t border-slate-800">
                    <td className="p-2">{factor}</td>
                    <td>{horizon ? `${horizon}${result?.frequency === "weekly" ? "周" : "日"}` : "—"}</td>
                    <td>{stats.ic_mean}</td>
                    <td>{stats.ic_std}</td>
                    <td>{stats.icir}</td>
                    <td>{stats.dates}</td>
                    <td>{stats.samples}</td>
                    <td className={good ? "text-emerald-400" : "text-slate-500"}>
                      {good ? "较有效" : "偏弱"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <TechnicalDetails data={result} />
        </div>
      )}
    </div>
  );
}
