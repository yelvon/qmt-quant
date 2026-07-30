import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EquityChart from "../components/EquityChart";

export default function ValidationPage() {
  const [params] = useSearchParams();
  const [fromRun, setFromRun] = useState(params.get("from") || "");
  const [runs, setRuns] = useState<{ id: string; label: string }[]>([]);
  const [match, setMatch] = useState("next_open");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => {
    apiGet<any[]>("/api/options/research-runs").then(setRuns);
  }, []);

  const onJob = useCallback(
    async (data: Record<string, unknown>) => {
      if (data.job_id !== jobId) return;
      setProgress(Number(data.progress || 0));
      setStatus(String(data.status || ""));
      if (data.status === "completed" && data.result) {
        const r = data.result as any;
        if (r.run_id) {
          const v = await apiGet<any>(`/api/validate/${r.run_id}`);
          setDetail(v.detail);
        } else setDetail(data.result);
      }
    },
    [jobId]
  );
  useJobProgress(onJob);

  async function runValidate() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/validate", {
      from_run: fromRun || undefined,
      match,
    });
    setJobId(res.job_id);
    setDetail(null);
  }

  return (
    <div>
      <PageCallout>仔细验策略：A 股 T+1、整手、费率规则。与 ③ 对比，给出「可以采用 / 建议复核」。</PageCallout>
      <div className="card grid gap-3 md:grid-cols-2">
        <PresetSelect
          label="来自研究 run"
          value={fromRun}
          options={[{ id: "", label: "手动参数" }, ...runs]}
          onChange={setFromRun}
        />
        <PresetSelect
          label="成交模式"
          value={match}
          options={[
            { id: "next_open", label: "次日开盘" },
            { id: "close", label: "当日收盘" },
          ]}
          onChange={setMatch}
        />
      </div>
      <button className="btn-primary mt-4" onClick={runValidate}>
        开始验证
      </button>
      {jobId && <JobProgressBar progress={progress} status={status} />}
      {detail && (
        <div className="card mt-4">
          <p className="text-lg font-medium text-emerald-400">结论：{detail.verdict}</p>
          <p className="text-sm text-slate-400">
            收益 {detail.total_return_pct}% · 回撤 {detail.max_drawdown_pct}% · 成交 {detail.trade_count}
          </p>
          {detail.equity_curve && <EquityChart title="验证净值" equity={detail.equity_curve} />}
        </div>
      )}
    </div>
  );
}
