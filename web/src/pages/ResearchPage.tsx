import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EquityChart from "../components/EquityChart";

export default function ResearchPage() {
  const nav = useNavigate();
  const [strategy, setStrategy] = useState("ma_cross");
  const [range, setRange] = useState("3y");
  const [shortP, setShortP] = useState("preset_std");
  const [longP, setLongP] = useState("preset_std");
  const [strategies, setStrategies] = useState<{ id: string; label: string }[]>([]);
  const [ranges, setRanges] = useState<{ id: string; label: string }[]>([]);
  const [ma, setMa] = useState<{ short: any[]; long: any[] }>({ short: [], long: [] });
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<any>(null);
  const [runId, setRunId] = useState("");
  const [wfOpen, setWfOpen] = useState(false);
  const [wfResult, setWfResult] = useState<any>(null);
  const [trainMonths, setTrainMonths] = useState(12);
  const [testMonths, setTestMonths] = useState(3);

  useEffect(() => {
    apiGet<any[]>("/api/options/strategies").then(setStrategies);
    apiGet<any[]>("/api/options/ranges").then(setRanges);
    apiGet<any>("/api/options/ma-presets").then(setMa);
  }, []);

  const onJob = useCallback(
    async (data: Record<string, unknown>) => {
      if (data.job_id !== jobId) return;
      setProgress(Number(data.progress || 0));
      setStatus(String(data.status || ""));
      if (data.status === "completed" && data.result) {
        const r = data.result as any;
        if (r.segments) {
          setWfResult(r);
          return;
        }
        setRunId(r.run_id);
        if (r.run_id) {
          const detail = await apiGet<any>(`/api/research/${r.run_id}`);
          setResult(detail.detail);
        }
      }
    },
    [jobId]
  );
  useJobProgress(onJob);

  async function runResearch() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/research", {
      strategy,
      range_preset: range,
      short_preset: shortP,
      long_preset: longP,
    });
    setJobId(res.job_id);
    setResult(null);
  }

  function sendToValidation() {
    nav(`/validation?from=${runId}`);
  }

  async function runWalkForward() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/research/walk-forward", {
      strategy,
      range_preset: range,
      short_preset: shortP,
      long_preset: longP,
      train_months: trainMonths,
      test_months: testMonths,
    });
    setJobId(res.job_id);
    setWfResult(null);
  }

  const combos = result?.combos || [];
  return (
    <div>
      <PageCallout>快速试策略：选预设参数包扫描，看热力图与最优组合。满意后送到 ④ 仔细验。</PageCallout>
      <div className="card grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <PresetSelect label="策略" value={strategy} options={strategies} onChange={setStrategy} />
        <PresetSelect label="区间" value={range} options={ranges} onChange={setRange} />
        <PresetSelect label="短均线包" value={shortP} options={ma.short} onChange={setShortP} />
        <PresetSelect label="长均线包" value={longP} options={ma.long} onChange={setLongP} />
      </div>
      <div className="mt-4 flex gap-2">
        <button className="btn-primary" onClick={runResearch}>
          开始扫描
        </button>
        {runId && (
          <button className="btn-secondary" onClick={sendToValidation}>
            送到仔细验策略
          </button>
        )}
      </div>
      {jobId && <JobProgressBar progress={progress} status={status} />}
      <details className="card mt-4" open={wfOpen} onToggle={(e) => setWfOpen((e.target as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer font-medium">Walk-Forward 稳健性</summary>
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
        <button className="btn-secondary mt-3" onClick={runWalkForward}>
          运行 Walk-Forward
        </button>
        {wfResult?.segments && (
          <p className="mt-2 text-sm text-emerald-400">
            稳健性 {wfResult.stability_score} · {wfResult.segment_count} 段
          </p>
        )}
      </details>
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
