import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { useBacktestMode } from "../lib/backtestMode";
import { parseApiError } from "../lib/errorMessages";
import { isValidationJob } from "../lib/jobTypes";
import { formatPastRunLabel, payloadErrorMessage, type PastRunOption } from "../lib/strategyUi";
import { useJobResultLoader } from "../lib/useJobResultLoader";
import { useJobTracker } from "../lib/useJobTracker";
import BacktestModeSwitch from "../components/BacktestModeSwitch";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EquityChart from "../components/EquityChart";
import ComparisonCard from "../components/ComparisonCard";
import EmptyState from "../components/EmptyState";
import StrategyErrorCard from "../components/StrategyErrorCard";
import TechnicalDetails from "../components/TechnicalDetails";
import StockReturnsTable from "../components/StockReturnsTable";

type RunOption = PastRunOption;

export default function ValidationPage() {
  const [params, setParams] = useSearchParams();
  const job = useJobTracker();
  const { isSimple, isSingle, setMode } = useBacktestMode();
  const validateActive = Boolean(job.jobId) && isValidationJob(job.jobType);

  const [fromRun, setFromRun] = useState(params.get("from") || "");
  const [runs, setRuns] = useState<RunOption[]>([]);
  const [validateHistory, setValidateHistory] = useState<RunOption[]>([]);
  const [match, setMatch] = useState("next_open");
  const [detail, setDetail] = useState<any>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [researchPreview, setResearchPreview] = useState<any>(null);
  const [historyValidateId, setHistoryValidateId] = useState("");

  const fromParam = params.get("from") || "";

  useEffect(() => {
    if (fromParam) {
      setFromRun(fromParam);
      setMode("research");
    }
  }, [fromParam, setMode]);

  useEffect(() => {
    apiGet<RunOption[]>("/api/options/research-runs").then(setRuns);
    apiGet<RunOption[]>("/api/options/validate-runs")
      .then(setValidateHistory)
      .catch(() => setValidateHistory([]));
  }, []);

  const loadValidationDetail = useCallback(async (id: string) => {
    const v = await apiGet<any>(`/api/validate/${id}`);
    if (v.error) {
      setPageError("找不到该验证记录");
      return;
    }
    setDetail(v.detail);
    setPageError(null);
  }, []);

  const applyValidationResult = useCallback(
    async (payload: Record<string, unknown>) => {
      const err = payloadErrorMessage(payload);
      if (err) {
        setPageError(err);
        setDetail(null);
        return;
      }
      const id = String(payload.run_id || "");
      if (id) {
        await loadValidationDetail(id);
        return;
      }
      setDetail(payload);
      setPageError(null);
    },
    [loadValidationDetail]
  );

  useJobResultLoader(validateActive, job.jobId, job.status, applyValidationResult);

  useEffect(() => {
    if (!fromRun) {
      setResearchPreview(null);
      return;
    }
    let cancelled = false;
    apiGet<any>(`/api/research/${fromRun}`)
      .then((res) => {
        if (!cancelled) setResearchPreview(res.detail || null);
      })
      .catch(() => {
        if (!cancelled) setResearchPreview(null);
      });
    return () => {
      cancelled = true;
    };
  }, [fromRun]);

  async function runValidate() {
    setSubmitting(true);
    setPageError(null);
    setDetail(null);
    try {
      const res = await apiPost<{ job_id: string }>("/api/jobs/validate", {
        from_run: fromRun || undefined,
        match,
        benchmark: "hs300",
      });
      job.trackJob(res.job_id, "仔细验策略运行中…", "validate");
    } catch (err) {
      setPageError(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setSubmitting(false);
    }
  }

  async function loadHistoryValidation(id: string) {
    setHistoryValidateId(id);
    if (!id) return;
    try {
      await loadValidationDetail(id);
    } catch (err) {
      setPageError(parseApiError(err instanceof Error ? err.message : String(err)));
    }
  }

  function pickResearchRun(id: string) {
    setFromRun(id);
    if (id) {
      setParams({ from: id });
    } else {
      setParams({});
    }
  }

  const qs = detail?.quantstats;
  const showEmpty = !detail && !validateActive && !pageError;

  const validateHistoryOptions = useMemo(
    () => validateHistory.map((r) => ({ id: r.id, label: formatPastRunLabel(r) })),
    [validateHistory]
  );

  if ((isSimple || isSingle) && !fromParam) {
    return (
      <div>
        <BacktestModeSwitch className="mb-4" />
        <PageCallout>
          当前为<strong className="font-normal text-slate-200">{isSingle ? "单股回测" : "简单回测"}</strong>
          模式：一次运行即可在 ③ 策略回测页看到结果。此页用于研究模式下的分步验证。
        </PageCallout>
        <EmptyState
          title={isSingle ? "单股模式下请使用 ③ 策略回测" : "简单模式下请使用 ③ 策略回测"}
          description={
            isSingle
              ? "搜索股票并点「运行回测」，即可查看该股策略净值与成交明细。"
              : "点一次「运行回测」即可完成参数筛选与 A 股规则验证，无需单独来本页。"
          }
          actionLabel="去策略回测"
          actionTo="/research"
        />
        <p className="mt-4 text-center text-sm text-slate-500">
          需要分步扫描参数、Walk-Forward 或手动挑组合验证？
          <button type="button" className="ml-1 text-emerald-400 underline" onClick={() => setMode("research")}>
            切换到研究扫描模式
          </button>
        </p>
      </div>
    );
  }

  return (
    <div>
      <BacktestModeSwitch className="mb-4" />

      <PageCallout>
        仔细验策略：A 股 T+1、整手、费率规则。与 ③ 扫描结果对比，给出「可以采用 / 建议复核」。
      </PageCallout>

      <div className="card grid gap-3 md:grid-cols-2">
        <PresetSelect
          label="选择③的结果"
          value={fromRun}
          options={[{ id: "", label: "不关联③（使用默认参数）" }, ...runs]}
          onChange={pickResearchRun}
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

      {fromRun && researchPreview?.best && (
        <p className="mt-2 text-xs text-slate-500">
          来自③：{researchPreview.best.label} · 快速扫描收益 {researchPreview.best.total_return_pct}%
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button className="btn-primary" disabled={job.isRunning || submitting} onClick={runValidate}>
          {submitting ? "提交中…" : "开始验证"}
        </button>
      </div>

      {pageError && (
        <StrategyErrorCard message={pageError} actionTo="/data" actionLabel="去准备数据" />
      )}

      {validateActive && (
        <div className="card mt-4">
          <JobProgressBar
            heading="仔细验策略"
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
        </div>
      )}

      {showEmpty && (
        <EmptyState
          title="还没有验证结果"
          description="请先从③研究扫描并「送到仔细验策略」，或选择已有研究记录后开始验证。"
          actionLabel="去研究扫描"
          actionTo="/research"
        />
      )}

      {validateHistory.length > 0 && (
        <details className="card mt-4">
          <summary className="cursor-pointer font-medium text-slate-200">找回以前的验证结果</summary>
          <p className="mt-2 text-sm text-slate-400">
            每次验证成功都会自动保存。选中一条即可重新打开当时的结论与净值曲线，不用重新跑任务。
          </p>
          <div className="mt-3 max-w-md">
            <PresetSelect
              label="选择一次验证"
              value={historyValidateId}
              options={[{ id: "", label: "请选择…" }, ...validateHistoryOptions]}
              onChange={loadHistoryValidation}
            />
          </div>
        </details>
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
            {!fromRun && (
              <p className="mt-2 text-xs text-amber-300/90">
                未关联③的研究记录，使用的是默认参数验证。
                <Link to="/research" className="ml-1 underline">
                  去研究扫描
                </Link>
              </p>
            )}
            <TechnicalDetails data={detail} />
          </div>
          {Array.isArray(detail.stock_returns) && detail.stock_returns.length > 1 && (
            <StockReturnsTable rows={detail.stock_returns} />
          )}
        </div>
      )}
    </div>
  );
}
