import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { useBacktestMode } from "../lib/backtestMode";
import { parseApiError } from "../lib/errorMessages";
import { isBacktestJob, isResearchJob } from "../lib/jobTypes";
import {
  formatPastRunLabel,
  payloadErrorMessage,
  researchCallout,
  simpleBacktestCallout,
  singleBacktestCallout,
  strategyAllowedInSingleMode,
  usesMaPresets,
  type PastRunOption,
} from "../lib/strategyUi";
import { useJobResultLoader } from "../lib/useJobResultLoader";
import { backtestDetailFromPayload } from "../lib/jobResult";
import { useJobTracker } from "../lib/useJobTracker";
import BacktestModeSwitch from "../components/BacktestModeSwitch";
import BacktestResultSkeleton from "../components/BacktestResultSkeleton";
import StockSearchInput from "../components/StockSearchInput";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EquityChart from "../components/EquityChart";
import ComparisonCard from "../components/ComparisonCard";
import EmptyState from "../components/EmptyState";
import StrategyErrorCard from "../components/StrategyErrorCard";
import TechnicalDetails from "../components/TechnicalDetails";

type RunOption = PastRunOption;

export default function ResearchPage() {
  const nav = useNavigate();
  const job = useJobTracker();
  const { isSimple, isResearch, isSingle, isPool } = useBacktestMode();

  const [strategy, setStrategy] = useState("ma_cross");
  const [sector, setSector] = useState("沪深A股");
  const [stockCode, setStockCode] = useState("");
  const [range, setRange] = useState("3y");
  const [shortP, setShortP] = useState("preset_std");
  const [longP, setLongP] = useState("preset_std");
  const [match, setMatch] = useState("next_open");
  const [strategies, setStrategies] = useState<{ id: string; label: string }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [ranges, setRanges] = useState<{ id: string; label: string }[]>([]);
  const [ma, setMa] = useState<{ short: RunOption[]; long: RunOption[] }>({ short: [], long: [] });
  const [historyRuns, setHistoryRuns] = useState<RunOption[]>([]);
  const [validateHistory, setValidateHistory] = useState<RunOption[]>([]);
  const [historyRunId, setHistoryRunId] = useState("");
  const [historyValidateId, setHistoryValidateId] = useState("");

  const [result, setResult] = useState<any>(null);
  const [runId, setRunId] = useState("");
  const [validateDetail, setValidateDetail] = useState<any>(null);
  const [validateRunId, setValidateRunId] = useState("");
  const [pageError, setPageError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resultFetchSlow, setResultFetchSlow] = useState(false);

  const [wfOpen, setWfOpen] = useState(false);
  const [wfResult, setWfResult] = useState<any>(null);
  const [trainMonths, setTrainMonths] = useState(12);
  const [testMonths, setTestMonths] = useState(3);

  const isBacktestLike = isSimple || isSingle;
  const jobType = job.jobType || (isBacktestLike ? "backtest" : "research");
  const backtestJobActive = Boolean(job.jobId) && isBacktestJob(jobType);
  const researchJobActive = Boolean(job.jobId) && isResearchJob(jobType);
  const wfJobActive = researchJobActive && jobType === "walk_forward";
  const scanJobActive = researchJobActive && jobType === "research";

  const showMaPresets = usesMaPresets(strategy) && isResearch;

  const strategyOptions = useMemo(
    () =>
      isSingle
        ? strategies.filter((s) => strategyAllowedInSingleMode(s.id))
        : strategies,
    [isSingle, strategies]
  );

  useEffect(() => {
    if (isSingle && !strategyAllowedInSingleMode(strategy) && strategyOptions.length) {
      setStrategy(strategyOptions[0].id);
    }
  }, [isSingle, strategy, strategyOptions]);

  function requireStock(): boolean {
    if (!isSingle) return true;
    if (stockCode.trim()) return true;
    setPageError("请先搜索并选择一只股票");
    return false;
  }

  function jobCodeField() {
    return isSingle && stockCode ? { code: stockCode } : {};
  }

  useEffect(() => {
    apiGet<any[]>("/api/options/strategies").then(setStrategies);
    apiGet<any[]>("/api/options/sectors").then(setSectors);
    apiGet<any[]>("/api/options/ranges").then(setRanges);
    apiGet<{ short: RunOption[]; long: RunOption[] }>("/api/options/ma-presets").then(setMa);
    apiGet<RunOption[]>("/api/options/research-runs").then(setHistoryRuns).catch(() => setHistoryRuns([]));
    apiGet<RunOption[]>("/api/options/validate-runs")
      .then(setValidateHistory)
      .catch(() => setValidateHistory([]));
  }, []);

  const loadResearchDetail = useCallback(async (id: string) => {
    const res = await apiGet<any>(`/api/research/${id}`);
    if (res.error) {
      setPageError("找不到该扫描记录");
      return;
    }
    setRunId(id);
    setResult(res.detail);
    setPageError(null);
  }, []);

  const loadValidationDetail = useCallback(async (id: string) => {
    const res = await apiGet<any>(`/api/validate/${id}`);
    if (res.error) {
      setPageError("找不到该回测记录");
      return;
    }
    setValidateRunId(id);
    setValidateDetail(res.detail);
    setPageError(null);
  }, []);

  const applyResearchResult = useCallback(
    async (payload: Record<string, unknown>) => {
      const err = payloadErrorMessage(payload);
      if (err) {
        setPageError(err);
        setResult(null);
        setRunId("");
        return;
      }
      if (payload.segments) {
        setWfResult(payload);
        setPageError(null);
        return;
      }
      const id = String(payload.run_id || "");
      if (!id) {
        setPageError("任务完成但未返回 run_id");
        return;
      }
      await loadResearchDetail(id);
    },
    [loadResearchDetail]
  );

  const applyBacktestResult = useCallback(
    async (payload: Record<string, unknown>) => {
      const err = payloadErrorMessage(payload);
      if (err) {
        setPageError(err);
        setValidateDetail(null);
        setValidateRunId("");
        return;
      }
      if (Array.isArray(payload.equity_curve) && payload.equity_curve.length > 0) {
        setValidateDetail(payload);
        setValidateRunId(String(payload.run_id || ""));
        setPageError(null);
        return;
      }
      const id = String(payload.run_id || "");
      if (id) {
        await loadValidationDetail(id);
        return;
      }
      setValidateDetail(payload);
      setPageError(null);
    },
    [loadValidationDetail]
  );

  useJobResultLoader(
    Boolean(job.jobId) && isResearchJob(job.jobType),
    job.jobId,
    job.status,
    applyResearchResult
  );
  useJobResultLoader(
    Boolean(job.jobId) && isBacktestJob(job.jobType),
    job.jobId,
    job.status,
    applyBacktestResult
  );

  const appliedJobResultRef = React.useRef("");
  useEffect(() => {
    if (job.status !== "completed" || !job.result) return;
    const key = `${job.jobId}:${String(job.result.run_id || "")}`;
    if (!key || appliedJobResultRef.current === key) return;

    const apply = async () => {
      if (isBacktestJob(job.jobType)) {
        await applyBacktestResult(job.result!);
        appliedJobResultRef.current = key;
        return;
      }
      if (isResearchJob(job.jobType)) {
        await applyResearchResult(job.result!);
        appliedJobResultRef.current = key;
      }
    };
    void apply();
  }, [job.jobId, job.jobType, job.status, job.result, applyBacktestResult, applyResearchResult]);

  useEffect(() => {
    if (job.status !== "completed" || !isBacktestLike || !isBacktestJob(jobType)) {
      setResultFetchSlow(false);
      return;
    }
    const inline = backtestDetailFromPayload(job.result);
    if (validateDetail || inline) {
      setResultFetchSlow(false);
      return;
    }
    const timer = window.setTimeout(() => setResultFetchSlow(true), 8000);
    return () => window.clearTimeout(timer);
  }, [job.status, job.result, jobType, isBacktestLike, validateDetail]);

  async function startJob(
    path: string,
    body: unknown,
    message: string,
    type: string,
    reset: () => void
  ) {
    setSubmitting(true);
    setPageError(null);
    reset();
    try {
      const res = await apiPost<{ job_id: string }>(path, body);
      job.trackJob(res.job_id, message, type);
    } catch (err) {
      setPageError(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setSubmitting(false);
    }
  }

  async function runBacktest() {
    if (!requireStock()) return;
    await startJob(
      "/api/jobs/backtest",
      {
        strategy,
        sector,
        range_preset: range,
        short_preset: shortP,
        long_preset: longP,
        match,
        benchmark: "hs300",
        ...jobCodeField(),
      },
      "策略回测运行中…",
      "backtest",
      () => {
        setValidateDetail(null);
        setValidateRunId("");
      }
    );
  }

  async function runResearch() {
    if (!requireStock()) return;
    await startJob(
      "/api/jobs/research",
      {
        strategy,
        sector,
        range_preset: range,
        short_preset: shortP,
        long_preset: longP,
        ...jobCodeField(),
      },
      "快速试策略扫描中…",
      "research",
      () => {
        setResult(null);
        setRunId("");
        setWfResult(null);
      }
    );
  }

  async function runWalkForward() {
    if (!requireStock()) return;
    if (!usesMaPresets(strategy)) {
      setPageError("Walk-Forward 目前仅支持「双均线」策略，请先切换策略。");
      return;
    }
    await startJob(
      "/api/jobs/research/walk-forward",
      {
        strategy,
        sector,
        range_preset: range,
        short_preset: shortP,
        long_preset: longP,
        train_months: trainMonths,
        test_months: testMonths,
        ...jobCodeField(),
      },
      "Walk-Forward 分析中…",
      "walk_forward",
      () => setWfResult(null)
    );
  }

  function sendToValidation() {
    if (!runId) return;
    nav(`/validation?from=${encodeURIComponent(runId)}`);
  }

  async function loadHistoryRun(id: string) {
    setHistoryRunId(id);
    if (!id) return;
    try {
      await loadResearchDetail(id);
    } catch (err) {
      setPageError(parseApiError(err instanceof Error ? err.message : String(err)));
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

  const combos = result?.combos || [];
  const wfSegments = wfResult?.segments || [];
  const hasScanResult = combos.length > 0;
  const hasWfResult = wfSegments.length > 0 || wfResult?.segment_count != null;
  const inlineBacktestDetail = useMemo(
    () =>
      job.status === "completed" && isBacktestJob(jobType)
        ? backtestDetailFromPayload(job.result)
        : null,
    [job.status, job.result, jobType]
  );
  const effectiveValidateDetail = validateDetail ?? inlineBacktestDetail;
  const hasBacktestResult = Boolean(
    effectiveValidateDetail &&
      Array.isArray(effectiveValidateDetail.equity_curve) &&
      effectiveValidateDetail.equity_curve.length > 0
  );
  const validateQs = effectiveValidateDetail?.quantstats;
  const backtestResultPending =
    job.status === "completed" &&
    isBacktestLike &&
    isBacktestJob(jobType) &&
    !hasBacktestResult &&
    !pageError;

  const pageJobActive =
    Boolean(job.jobId) &&
    (job.isRunning ||
      job.status === "pending" ||
      (job.status === "completed" && isResearch && !hasScanResult && !hasWfResult));

  const showEmptyBacktestLike =
    isBacktestLike &&
    !hasBacktestResult &&
    !hasScanResult &&
    !pageError &&
    !(Boolean(job.jobId) && (job.isRunning || (job.status === "completed" && !hasBacktestResult)));
  const showEmptyResearch =
    isResearch && !hasScanResult && !hasWfResult && !researchJobActive && !pageError && !backtestJobActive;

  const progressHeading = useMemo(() => {
    if (backtestJobActive) return "策略回测";
    if (wfJobActive) return "Walk-Forward 分析";
    if (scanJobActive) return "快速试策略扫描";
    return "策略任务";
  }, [backtestJobActive, wfJobActive, scanJobActive]);

  const historyOptions = useMemo(
    () => historyRuns.map((r) => ({ id: r.id, label: formatPastRunLabel(r) })),
    [historyRuns]
  );

  const validateHistoryOptions = useMemo(
    () => validateHistory.map((r) => ({ id: r.id, label: formatPastRunLabel(r) })),
    [validateHistory]
  );

  return (
    <div>
      <BacktestModeSwitch className="mb-4" />

      <PageCallout>
        {isSingle
          ? singleBacktestCallout(strategy)
          : isSimple
            ? simpleBacktestCallout(strategy)
            : researchCallout(strategy)}
      </PageCallout>

      {isSingle && (
        <div className="card mb-4 max-w-md">
          <StockSearchInput label="回测股票" value={stockCode} onChange={setStockCode} />
        </div>
      )}

      <div className="card grid gap-3 md:grid-cols-2 lg:grid-cols-5">
        <PresetSelect
          label="策略"
          value={strategy}
          options={strategyOptions}
          onChange={setStrategy}
        />
        {isPool && (
          <PresetSelect label="股票池" value={sector} options={sectors} onChange={setSector} />
        )}
        <PresetSelect label="区间" value={range} options={ranges} onChange={setRange} />
        {isBacktestLike ? (
          <PresetSelect
            label="成交模式"
            value={match}
            options={[
              { id: "next_open", label: "次日开盘" },
              { id: "close", label: "当日收盘" },
            ]}
            onChange={setMatch}
          />
        ) : showMaPresets ? (
          <>
            <PresetSelect label="短均线包" value={shortP} options={ma.short} onChange={setShortP} />
            <PresetSelect label="长均线包" value={longP} options={ma.long} onChange={setLongP} />
          </>
        ) : (
          <div className="lg:col-span-2 rounded-lg border border-dashed border-slate-700 px-3 py-2 text-xs text-slate-500">
            当前策略无需均线参数包
          </div>
        )}
      </div>

      {strategy === "pe_momentum" && (
        <p className="mt-2 text-xs text-amber-300/90">
          低估值 + 动量依赖财报中的 PE 数据；若尚未同步财报，结果可能无效。
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {isBacktestLike ? (
          <>
            <button className="btn-primary" disabled={job.isRunning || submitting} onClick={runBacktest}>
              {submitting ? "提交中…" : "运行回测"}
            </button>
            {isSingle && usesMaPresets(strategy) && (
              <button
                className="btn-secondary"
                disabled={job.isRunning || submitting}
                onClick={runResearch}
              >
                扫描该股参数
              </button>
            )}
          </>
        ) : (
          <>
            <button className="btn-primary" disabled={job.isRunning || submitting} onClick={runResearch}>
              {submitting ? "提交中…" : "开始扫描"}
            </button>
            {runId && (
              <button className="btn-secondary" onClick={sendToValidation}>
                送到仔细验策略
              </button>
            )}
          </>
        )}
      </div>

      {pageError && (
        <StrategyErrorCard message={pageError} actionTo="/data" actionLabel="去准备数据" />
      )}

      {backtestResultPending && (
        <BacktestResultSkeleton
          message={
            resultFetchSlow
              ? "结果仍在写入，请稍候；也可在下方「找回以前的回测结果」手动打开"
              : "正在整理回测结果…"
          }
        />
      )}

      {pageJobActive && (
        <div className="card mt-4">
          <JobProgressBar
            heading={progressHeading}
            progress={job.progress}
            status={job.status}
            message={job.message}
            error={job.error}
            jobType={jobType}
            step={job.step}
            detail={job.detail}
            etaSeconds={job.etaSeconds}
            completeAction={
              job.status === "completed" && isResearch && runId
                ? { label: "送到仔细验策略", onClick: sendToValidation }
                : job.status === "completed" && isBacktestLike && effectiveValidateDetail?.verdict === "可以采用"
                  ? { label: "去模拟下单", to: "/live" }
                  : undefined
            }
            onCancel={() => job.cancelJob()}
            cancelling={job.cancelling}
          />
        </div>
      )}

      {isResearch && (
        <details
          className="card mt-4"
          open={wfOpen || wfJobActive}
          onToggle={(e) => setWfOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary className="cursor-pointer font-medium">Walk-Forward 稳健性（双均线）</summary>
          <p className="mt-2 text-sm text-slate-400">
            在 train 段选最优参数，在 test 段看样本外收益。stability 越高说明越稳健。
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <label className="label">Train 月数</label>
              <input
                className="input w-full"
                type="number"
                min={3}
                value={trainMonths}
                onChange={(e) => setTrainMonths(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="label">Test 月数</label>
              <input
                className="input w-full"
                type="number"
                min={1}
                value={testMonths}
                onChange={(e) => setTestMonths(Number(e.target.value))}
              />
            </div>
          </div>
          <button
            className="btn-secondary mt-3"
            disabled={job.isRunning || submitting || !usesMaPresets(strategy)}
            onClick={runWalkForward}
          >
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
      )}

      {showEmptyBacktestLike && (
        <EmptyState
          title={isSingle ? "还没有单股回测结果" : "还没有回测结果"}
          description={
            isSingle
              ? "搜索并选择股票，点上方「运行回测」。完成后这里会显示净值曲线与成交明细。"
              : "选好策略和区间，点上方「运行回测」。完成后这里会显示净值曲线与收益指标。"
          }
        />
      )}

      {showEmptyResearch && (
        <EmptyState
          title="还没有扫描结果"
          description="选好策略和区间，点上方「开始扫描」。完成后这里会显示参数收益柱状图。"
        />
      )}

      {isBacktestLike && validateHistory.length > 0 && (
        <details className="card mt-4">
          <summary className="cursor-pointer font-medium text-slate-200">
            {isSingle ? "找回以前的单股回测" : "找回以前的回测结果"}
          </summary>
          <p className="mt-2 text-sm text-slate-400">
            每次回测成功都会自动保存。选中一条即可重新打开当时的净值曲线，不用重新跑任务。
          </p>
          <div className="mt-3 max-w-md">
            <PresetSelect
              label="选择一次回测"
              value={historyValidateId || validateRunId}
              options={[{ id: "", label: "请选择…" }, ...validateHistoryOptions]}
              onChange={loadHistoryValidation}
            />
          </div>
        </details>
      )}

      {isResearch && historyRuns.length > 0 && (
        <details className="card mt-4">
          <summary className="cursor-pointer font-medium text-slate-200">找回以前的扫描结果</summary>
          <p className="mt-2 text-sm text-slate-400">
            每次扫描成功都会自动保存。选中一条即可重新打开当时的柱状图，不用重新跑任务。
          </p>
          <div className="mt-3 max-w-md">
            <PresetSelect
              label="选择一次扫描"
              value={historyRunId || runId}
              options={[{ id: "", label: "请选择…" }, ...historyOptions]}
              onChange={loadHistoryRun}
            />
          </div>
        </details>
      )}

      {isBacktestLike && hasBacktestResult && !researchJobActive && (
        <div id="backtest-results" className="mt-4 space-y-4">
          <ComparisonCard
            comparison={effectiveValidateDetail.comparison}
            verdict={effectiveValidateDetail.verdict}
            totalReturnPct={effectiveValidateDetail.total_return_pct}
            variant={isSingle ? "simple" : isSimple ? "simple" : "research"}
          />
          <div className="card">
            {(effectiveValidateDetail.codes?.[0] || stockCode) && (
              <p className="text-sm font-medium text-slate-200">
                {effectiveValidateDetail.codes?.[0] || stockCode}
              </p>
            )}
            <p className="text-sm text-slate-400">
              回撤 {effectiveValidateDetail.max_drawdown_pct}% · 成交 {effectiveValidateDetail.trade_count} 笔
            </p>
            {validateQs && (
              <p className="mt-2 text-sm text-slate-300">
                夏普 {validateQs.sharpe ?? "—"} · 胜率 {validateQs.win_rate_pct ?? "—"}% · 波动{" "}
                {validateQs.volatility_pct ?? "—"}%
              </p>
            )}
            {effectiveValidateDetail.equity_curve && (
              <EquityChart
                title={isSingle ? "单股策略净值 vs 沪深300" : "策略净值 vs 沪深300"}
                equity={effectiveValidateDetail.equity_curve}
                benchmark={effectiveValidateDetail.benchmark_curve}
              />
            )}
            {isSingle && effectiveValidateDetail.trades?.length > 0 && (
              <div className="mt-4 overflow-x-auto">
                <p className="mb-2 text-sm font-medium text-slate-300">成交明细</p>
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-slate-500">
                    <tr>
                      <th className="pb-2 pr-3">日期</th>
                      <th className="pb-2 pr-3">方向</th>
                      <th className="pb-2 pr-3">价格</th>
                      <th className="pb-2 pr-3">数量</th>
                      <th className="pb-2">费用</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-300">
                    {effectiveValidateDetail.trades.map((t: any, i: number) => (
                      <tr key={`${t.date}-${t.side}-${i}`} className="border-t border-slate-800">
                        <td className="py-2 pr-3">{t.date}</td>
                        <td className="py-2 pr-3">{t.side}</td>
                        <td className="py-2 pr-3">{t.price}</td>
                        <td className="py-2 pr-3">{t.quantity}</td>
                        <td className="py-2">{t.fee}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {effectiveValidateDetail.research_best && (
              <p className="mt-2 text-xs text-slate-500">
                后台选用参数：{effectiveValidateDetail.research_best.label}（快速扫描收益{" "}
                {effectiveValidateDetail.research_best.total_return_pct}%）
              </p>
            )}
            <details className="mt-3">
              <summary className="cursor-pointer text-xs text-slate-500">想自己挑参数？切换到研究扫描模式</summary>
              <p className="mt-1 text-xs text-slate-500">
                研究模式下可查看全部参数组合的柱状图，并分步送到 ④ 仔细验。
                <Link to="/validation" className="ml-1 underline">
                  或直接去验证页
                </Link>
              </p>
            </details>
            <TechnicalDetails data={effectiveValidateDetail} />
          </div>
        </div>
      )}

      {isSingle && hasScanResult && !backtestJobActive && (
        <div className="card mt-4">
          <EquityChart
            title="该股参数组合收益（柱状越高越好）"
            categories={combos.map((c: any) => c.label)}
            values={combos.map((c: any) => c.total_return_pct)}
          />
          <p className="mt-2 text-sm text-emerald-400">
            最优：{result?.best?.label} · 收益 {result?.best?.total_return_pct}%
          </p>
          <p className="mt-2 text-xs text-slate-500">
            以上为该股快速扫描结果。点「运行回测」会用较优参数做 A 股规则验证。
          </p>
        </div>
      )}

      {isResearch && hasScanResult && !backtestJobActive && (
        <div className="card mt-4">
          <EquityChart
            title={showMaPresets ? "参数组合收益（柱状越高越好）" : "策略收益"}
            categories={combos.map((c: any) => c.label)}
            values={combos.map((c: any) => c.total_return_pct)}
          />
          <p className="mt-2 text-sm text-emerald-400">
            最优：{result?.best?.label} · 收益 {result?.best?.total_return_pct}%
          </p>
          {result?.quantstats && (
            <p className="text-sm text-slate-300">
              夏普 {result.quantstats.sharpe ?? "—"} · 最大回撤{" "}
              {result.quantstats.max_drawdown_pct ?? "—"}%
            </p>
          )}
          <p className="mt-2 text-xs text-slate-500">
            以上为快速扫描结果（VectorBT，简化费率）。重要决策请用 ④ 仔细验策略复核。
          </p>
        </div>
      )}
    </div>
  );
}
