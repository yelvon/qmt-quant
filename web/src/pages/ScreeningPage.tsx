import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EmptyState from "../components/EmptyState";

const RULE_PRESETS = [
  { id: "", label: "使用上方模板（默认）" },
  { id: "strategies/rules/low_pe_momentum.yaml", label: "低估值动量 YAML" },
];

export default function ScreeningPage() {
  const nav = useNavigate();
  const [template, setTemplate] = useState("low_pe");
  const [sector, setSector] = useState("沪深A股");
  const [peMax, setPeMax] = useState(30);
  const [roeMin, setRoeMin] = useState(0.1);
  const [topN, setTopN] = useState(30);
  const [excludeSt, setExcludeSt] = useState(true);
  const [rulePath, setRulePath] = useState("");
  const [templates, setTemplates] = useState<{ id: string; label: string }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const [jobError, setJobError] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);
  const [runId, setRunId] = useState("");

  useEffect(() => {
    apiGet<any[]>("/api/options/templates").then(setTemplates);
    apiGet<any[]>("/api/options/sectors").then(setSectors);
  }, []);

  const onJob = useCallback(
    (data: Record<string, unknown>) => {
      if (data.job_id !== jobId) return;
      setProgress(Number(data.progress || 0));
      setStatus(String(data.status || ""));
      if (data.error) setJobError(String(data.error));
      if (data.status === "completed" && data.result) {
        setJobError(null);
        const r = data.result as any;
        setResults(r.results || []);
        setRunId(r.run_id || "");
      }
    },
    [jobId]
  );
  useJobProgress(onJob);

  async function runScreen() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/screen", {
      template,
      sector,
      top: topN,
      exclude_st: excludeSt,
      pe_max: peMax,
      roe_min: roeMin,
      rule_path: rulePath || undefined,
    });
    setJobId(res.job_id);
    setResults([]);
    setRunId("");
  }

  async function sendToResearch() {
    if (!runId) return;
    await apiPost("/api/jobs/research", {
      strategy: "screening_rebalance",
      screen_run_id: runId,
    });
    nav("/research");
  }

  async function sendToValidation() {
    if (!runId) return;
    await apiPost("/api/jobs/validate", {
      strategy: "screening_rebalance",
      screen_run_id: runId,
    });
    nav("/validation");
  }

  return (
    <div>
      <PageCallout>选股：可视化条件 + 模板，结果可桥接到 ③/④ 作为股票池。</PageCallout>
      <div className="card grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        <PresetSelect label="模板" value={template} options={templates} onChange={setTemplate} />
        <PresetSelect label="范围" value={sector} options={sectors} onChange={setSector} />
        <div>
          <label className="label">PE 上限</label>
          <input
            className="input w-full"
            type="number"
            value={peMax}
            onChange={(e) => setPeMax(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="label">ROE 下限</label>
          <input
            className="input w-full"
            type="number"
            step="0.01"
            value={roeMin}
            onChange={(e) => setRoeMin(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="label">Top N</label>
          <input
            className="input w-full"
            type="number"
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={excludeSt} onChange={(e) => setExcludeSt(e.target.checked)} />
          排除 ST
        </label>
      </div>
      <details className="card mt-4">
        <summary className="cursor-pointer font-medium">高级：YAML 规则</summary>
        <div className="mt-3">
          <PresetSelect
            label="规则预设"
            value={rulePath}
            options={RULE_PRESETS}
            onChange={setRulePath}
          />
        </div>
      </details>
      <button className="btn-primary mt-4" onClick={runScreen}>
        开始选股
      </button>
      {jobId && <JobProgressBar progress={progress} status={status} error={jobError} />}
      {!results.length && !jobId && (
        <EmptyState title="还没有选股结果" description="选择模板与条件后点击「开始选股」。" />
      )}
      {runId && (
        <div className="mt-4 flex gap-2">
          <button className="btn-secondary" onClick={sendToResearch}>
            送到快速试策略
          </button>
          <button className="btn-secondary" onClick={sendToValidation}>
            送到仔细验策略
          </button>
        </div>
      )}
      {results.length > 0 && (
        <div className="card mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="p-2">代码</th>
                <th>名称</th>
                <th>PE</th>
                <th>ROE</th>
                <th>得分</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.code} className="border-t border-slate-800">
                  <td className="p-2">{r.code}</td>
                  <td>{r.name || "—"}</td>
                  <td>{r.pe}</td>
                  <td>{r.roe}</td>
                  <td>{r.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
