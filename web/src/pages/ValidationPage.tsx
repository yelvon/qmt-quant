import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { fetchJobRecord, resultFromJobRecord } from "../lib/jobResult";
import { isValidationJob } from "../lib/jobTypes";
import { useJobTracker } from "../lib/useJobTracker";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EquityChart from "../components/EquityChart";
import ComparisonCard from "../components/ComparisonCard";
import EmptyState from "../components/EmptyState";
import TechnicalDetails from "../components/TechnicalDetails";

export default function ValidationPage() {
  const [params] = useSearchParams();
  const job = useJobTracker();
  const validateActive = Boolean(job.jobId) && isValidationJob(job.jobType);

  const [fromRun, setFromRun] = useState(params.get("from") || "");
  const [runs, setRuns] = useState<{ id: string; label: string }[]>([]);
  const [match, setMatch] = useState("next_open");
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => {
    apiGet<any[]>("/api/options/research-runs").then(setRuns);
  }, []);

  async function applyValidationResult(payload: Record<string, unknown>) {
    const id = String(payload.run_id || "");
    if (id) {
      const v = await apiGet<any>(`/api/validate/${id}`);
      setDetail(v.detail);
      return;
    }
    setDetail(payload);
  }

  useEffect(() => {
    if (!validateActive || !job.jobId || job.status !== "completed") return;
    let cancelled = false;
    (async () => {
      try {
        const record = await fetchJobRecord(job.jobId);
        const payload = resultFromJobRecord(record);
        if (!payload || cancelled) return;
        await applyValidationResult(payload);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [validateActive, job.jobId, job.status]);

  async function runValidate() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/validate", {
      from_run: fromRun || undefined,
      match,
      benchmark: "hs300",
    });
    setDetail(null);
    job.trackJob(res.job_id, "仔细验策略运行中…", "validate");
  }

  const qs = detail?.quantstats;

  return (
    <div>
      <PageCallout>仔细验策略：A 股 T+1、整手、费率规则。与 ③ 对比，给出「可以采用 / 建议复核」。</PageCallout>
      <div className="card grid gap-3 md:grid-cols-2">
        <PresetSelect
          label="选择③的结果"
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
      <button className="btn-primary mt-4" disabled={job.isRunning} onClick={runValidate}>
        开始验证
      </button>
      {validateActive && (
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
            job.status === "completed" && detail?.verdict === "可以采用"
              ? { label: "去模拟下单", to: "/live" }
              : undefined
          }
        />
      )}
      {!detail && !validateActive && (
        <EmptyState
          title="还没有验证结果"
          description="请先从③快速试策略，再送到本页验证；或选择已有研究记录。"
          actionLabel="去快速试策略"
          actionTo="/research"
        />
      )}
      {detail && (
        <div className="mt-4 space-y-4">
          <ComparisonCard
            comparison={detail.comparison}
            verdict={detail.verdict}
            totalReturnPct={detail.total_return_pct}
          />
          <div className="card">
            <p className="text-sm text-slate-400">
              回撤 {detail.max_drawdown_pct}% · 成交 {detail.trade_count} 笔
            </p>
            {qs && (
              <p className="mt-2 text-sm text-slate-300">
                夏普 {qs.sharpe ?? "—"} · 胜率 {qs.win_rate_pct ?? "—"}% · 波动 {qs.volatility_pct ?? "—"}%
              </p>
            )}
            {detail.equity_curve && (
              <EquityChart
                title="验证净值 vs 沪深300"
                equity={detail.equity_curve}
                benchmark={detail.benchmark_curve}
              />
            )}
            <TechnicalDetails data={detail} />
          </div>
        </div>
      )}
    </div>
  );
}
