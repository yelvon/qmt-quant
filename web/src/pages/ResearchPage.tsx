import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { fetchJobRecord, resultFromJobRecord } from "../lib/jobResult";
import { isResearchJob } from "../lib/jobTypes";
import { useJobTracker } from "../lib/useJobTracker";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EquityChart from "../components/EquityChart";
import EmptyState from "../components/EmptyState";

export default function ResearchPage() {
  const nav = useNavigate();
  const job = useJobTracker();
  const researchActive = Boolean(job.jobId) && isResearchJob(job.jobType);

  const [strategy, setStrategy] = useState("ma_cross");
  const [sector, setSector] = useState("沪深A股");
  const [range, setRange] = useState("3y");
  const [shortP, setShortP] = useState("preset_std");
  const [longP, setLongP] = useState("preset_std");
  const [strategies, setStrategies] = useState<{ id: string; label: string }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [ranges, setRanges] = useState<{ id: string; label: string }[]>([]);
  const [ma, setMa] = useState<{ short: any[]; long: any[] }>({ short: [], long: [] });
  const [result, setResult] = useState<any>(null);
  const [runId, setRunId] = useState("");
  const [wfOpen, setWfOpen] = useState(false);
  const [wfResult, setWfResult] = useState<any>(null);
  const [trainMonths, setTrainMonths] = useState(12);
  const [testMonths, setTestMonths] = useState(3);

  useEffect(() => {
    apiGet<any[]>("/api/options/strategies").then(setStrategies);
    apiGet<any[]>("/api/options/sectors").then(setSectors);
    apiGet<any[]>("/api/options/ranges").then(setRanges);
    apiGet<any>("/api/options/ma-presets").then(setMa);
  }, []);

  async function applyResearchResult(payload: Record<string, unknown>) {
    if (payload.segments) {
      setWfResult(payload);
      return;
    }
    const id = String(payload.run_id || "");
    if (!id) return;
    setRunId(id);
    const detail = await apiGet<any>(`/api/research/${id}`);
    setResult(detail.detail);
  }

  useEffect(() => {
    if (!researchActive || !job.jobId || job.status !== "completed") return;
    let cancelled = false;
    (async () => {
      try {
        const record = await fetchJobRecord(job.jobId);
        const payload = resultFromJobRecord(record);
        if (!payload || cancelled) return;
        await applyResearchResult(payload);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [researchActive, job.jobId, job.status]);

  async function runResearch() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/research", {
      strategy,
      sector,
      range_preset: range,
      short_preset: shortP,
      long_preset: longP,
    });
    setResult(null);
    setRunId("");
    setWfResult(null);
    job.trackJob(res.job_id, "快速试策略扫描中…", "research");
  }

  function sendToValidation() {
    nav(`/validation?from=${runId}`);
  }

  async function runWalkForward() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/research/walk-forward", {
      strategy,
      sector,
      range_preset: range,
      short_preset: shortP,
      long_preset: longP,
      train_months: trainMonths,
      test_months: testMonths,
    });
    setWfResult(null);
    job.trackJob(res.job_id, "Walk-Forward 分析中…", "walk_forward");
  }

  const combos = result?.combos || [];
  const wfSegments = wfResult?.segments || [];

  return (
    <div>
      <PageCallout>快速试策略：选预设参数包扫描，看热力图与最优组合。满意后送到 ④ 仔细验。</PageCallout>
      <div className="card grid gap-3 md:grid-cols-2 lg:grid-cols-5">
        <PresetSelect label="策略" value={strategy} options={strategies} onChange={setStrategy} />
        <PresetSelect label="股票池" value={sector} options={sectors} onChange={setSector} />
        <PresetSelect label="区间" value={range} options={ranges} onChange={setRange} />
        <PresetSelect label="短均线包" value={shortP} options={ma.short} onChange={setShortP} />
        <PresetSelect label="长均线包" value={longP} options={ma.long} onChange={setLongP} />
      </div>
      <div className="mt-4 flex gap-2">
        <button className="btn-primary" disabled={job.isRunning} onClick={runResearch}>
          开始扫描
        </button>
        {runId && (
          <button className="btn-secondary" onClick={sendToValidation}>
            送到仔细验策略
          </button>
        )}
      </div>
      {researchActive && (
        <JobProgressBar
          progress={job.progress}
          status={job.status}
          message={job.message}
          error={job.error}
          jobType={job.jobType}
          step={job.step}
          detail={job.detail}
          etaSeconds={job.etaSeconds}
          completeAction={
            job.status === "completed" && runId
              ? { label: "送到仔细验策略", onClick: sendToValidation }
              : undefined
          }
        />
      )}
      <details className="card mt-4" open={wfOpen} onToggle={(e) => setWfOpen((e.target as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer font-medium">Walk-Forward 稳健性</summary>
        <p className="mt-2 text-sm text-slate-400">
          在 train 段选最优参数，在 test 段看样本外收益。stability 越高说明越稳健，避免过拟合。
        </p>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div>
            <label className="label">Train 月数</label>
            <input
              className="input w-full"
              type="number"
              value={trainMonths}
              onChange={(e) => setTrainMonths(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Test 月数</label>
            <input
              className="input w-full"
              type="number"
              value={testMonths}
              onChange={(e) => setTestMonths(Number(e.target.value))}
            />
          </div>
        </div>
        <button className="btn-secondary mt-3" disabled={job.isRunning} onClick={runWalkForward}>
          运行 Walk-Forward
        </button>
        {wfResult?.segment_count != null && (
          <p className="mt-2 text-sm text-emerald-400">
            稳健性 {wfResult.stability_score} · {wfResult.segment_count} 段
          </p>
        )}
        {wfSegments.length > 0 && (
          <div className="mt-4">
            <EquityChart
              title="各段样本外收益 (OOS %)"
              categories={wfSegments.map((s: any) => `${s.test_start}`)}
              values={wfSegments.map((s: any) => s.oos_return_pct)}
            />
          </div>
        )}
      </details>
      {combos.length === 0 && !researchActive && (
        <EmptyState
          title="还没有扫描结果"
          description="选择策略与参数预设后点击「开始扫描」。"
        />
      )}
      {combos.length > 0 && (
        <div className="card mt-4">
          <EquityChart
            title="参数组合收益"
            categories={combos.map((c: any) => c.label)}
            values={combos.map((c: any) => c.total_return_pct)}
          />
          <p className="mt-2 text-sm text-emerald-400">
            最优：{result?.best?.label} · 收益 {result?.best?.total_return_pct}%
          </p>
          {result?.quantstats && (
            <p className="text-sm text-slate-300">
              夏普 {result.quantstats.sharpe ?? "—"} · 回撤 {result.quantstats.max_drawdown_pct ?? "—"}%
            </p>
          )}
        </div>
      )}
    </div>
  );
}
