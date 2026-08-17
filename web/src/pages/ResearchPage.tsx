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
  strategyAllowedInPoolMode,
  strategyAllowedInSingleMode,
  usesMaPresets,
  type PastRunOption,
} from "../lib/strategyUi";
import { useJobResultLoader } from "../lib/useJobResultLoader";
import { backtestDetailFromPayload } from "../lib/jobResult";
import { useJobTracker } from "../lib/useJobTracker";
import BacktestModeSwitch from "../components/BacktestModeSwitch";
import BacktestResultSkeleton from "../components/BacktestResultSkeleton";
import StockReturnsTable from "../components/StockReturnsTable";
import StockSearchInput from "../components/StockSearchInput";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EquityChart from "../components/EquityChart";
import ComparisonCard from "../components/ComparisonCard";
import EmptyState from "../components/EmptyState";
import StrategyErrorCard from "../components/StrategyErrorCard";
import TechnicalDetails from "../components/TechnicalDetails";
import SingleStockTradeView from "../components/SingleStockTradeView";

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
  const [barFrequency, setBarFrequency] = useState("daily");
  const [strategies, setStrategies] = useState<{ id: string; label: string }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [ranges, setRanges] = useState<{ id: string; label: string }[]>([]);
  const [ma, setMa] = useState<{ short: RunOption[]; long: RunOption[] }>({ short: [], long: [] });
  const [historyRuns, setHistoryRuns] = useState<RunOption[]>([]);
  const [validateHistory, setValidateHistory] = useState<RunOption[]>([]);
  const [historyRunId, setHistoryRunId] = useState("");
  const [historyValidateId, setHistoryValidateId] = useState("");

  const [universeInfo, setUniverseInfo] = useState<{
    pool_size: number;
    used: number;
    capped: boolean;
    cap: number | null;
    sample?: string;
    sample_label?: string;
    sample_fallback?: string | null;
  } | null>(null);
  const [sampleMode, setSampleMode] = useState("all");
  const [universeN, setUniverseN] = useState("");
  const [signalText, setSignalText] = useState("");

  const [result, setResult] = useState<any>(null);
  const [runId, setRunId] = useState("");
  const [validateDetail, setValidateDetail] = useState<any>(null);
  const [validateRunId, setValidateRunId] = useState("");
  const [pageError, setPageError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resultFetchSlow, setResultFetchSlow] = useState(false);

  const [wfOpen, setWfOpen] = useState(false);
  const [wfResult, setWfResult] = useState<any>(null);
  const [trainBars, setTrainBars] = useState(252);
  const [testBars, setTestBars] = useState(63);
  const [purgeBars, setPurgeBars] = useState(0);
  const [embargoBars, setEmbargoBars] = useState(0);

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
        : strategies.filter((s) => strategyAllowedInPoolMode(s.id)),
    [isSingle, strategies]
  );

  useEffect(() => {
    if (isSingle && !strategyAllowedInSingleMode(strategy) && strategyOptions.length) {
      setStrategy(strategyOptions[0].id);
    }
    if (!isSingle && !strategyAllowedInPoolMode(strategy) && strategyOptions.length) {
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

  function samplingFields() {
    if (!isPool || sector !== "沪深A股") return {};
    return {
      sample: sampleMode,
      ...(universeN ? { universe_n: Number(universeN) } : {}),
    };
  }

  function parsedSignals() {
    const rows: { date: string; side: string }[] = [];
    for (const line of signalText.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.toLowerCase().startsWith("date")) continue;
      const parts = trimmed.split(/[,;\t ]+/);
      if (parts.length < 2) continue;
      rows.push({ date: parts[0].slice(0, 10), side: parts[1] });
    }
    return rows;
  }

  useEffect(() => {
    apiGet<any[]>("/api/options/strategies").then(setStrategies);
    const loadSectors = () => apiGet<any[]>("/api/options/sectors").then(setSectors);
    loadSectors();
    window.addEventListener("focus", loadSectors);
    apiGet<any[]>("/api/options/ranges").then(setRanges);
    apiGet<{ short: RunOption[]; long: RunOption[] }>("/api/options/ma-presets").then(setMa);
    apiGet<RunOption[]>("/api/options/research-runs").then(setHistoryRuns).catch(() => setHistoryRuns([]));
    apiGet<RunOption[]>("/api/options/validate-runs")
      .then(setValidateHistory)
      .catch(() => setValidateHistory([]));
    return () => window.removeEventListener("focus", loadSectors);
  }, []);

  useEffect(() => {
    if (!isPool) {
      setUniverseInfo(null);
      return;
    }
    const qs = new URLSearchParams({
      sector,
      strategy,
      sample: sampleMode,
      range_preset: range,
    });
    if (universeN) qs.set("universe_n", universeN);
    apiGet<{
      pool_size: number;
      used: number;
      capped: boolean;
      cap: number | null;
      sample?: string;
      sample_label?: string;
      sample_fallback?: string | null;
    }>(`/api/options/research-universe?${qs.toString()}`)
      .then(setUniverseInfo)
      .catch(() => setUniverseInfo(null));
  }, [sector, strategy, isPool, sampleMode, universeN, range]);

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
        bar_frequency: barFrequency,
        ...jobCodeField(),
        ...samplingFields(),
        ...(strategy === "signal_replay" ? { signals: parsedSignals() } : {}),
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
        bar_frequency: barFrequency,
        ...jobCodeField(),
        ...samplingFields(),
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
    await startJob(
      "/api/jobs/research/walk-forward",
      {
        strategy,
        sector,
        range_preset: range,
        short_preset: shortP,
        long_preset: longP,
        train_bars: trainBars,
        test_bars: testBars,
        bar_frequency: barFrequency,
        window_type: "rolling",
        purge_bars: purgeBars,
        embargo_bars: embargoBars,
        ...jobCodeField(),
        ...samplingFields(),
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
        {isPool && sector === "沪深A股" && (
          <>
            <PresetSelect
              label="抽样"
              value={sampleMode}
              options={[
                { id: "all", label: "全部（默认）" },
                { id: "turnover", label: "期初近20日成交额" },
              ]}
              onChange={setSampleMode}
            />
            <PresetSelect
              label="抽样只数"
              value={universeN}
              options={[
                { id: "", label: "不限" },
                { id: "50", label: "50" },
                { id: "100", label: "100" },
                { id: "300", label: "300" },
              ]}
              onChange={setUniverseN}
            />
          </>
        )}
        <PresetSelect label="区间" value={range} options={ranges} onChange={setRange} />
        <PresetSelect
          label="K 线周期"
          value={barFrequency}
          options={[
            { id: "daily", label: "日线" },
            { id: "weekly", label: "周线" },
          ]}
          onChange={setBarFrequency}
        />
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
      <p className="mt-2 text-xs text-slate-400">
        {barFrequency === "weekly"
          ? "周线由本地日线按实际交易日聚合；周末最后交易日收盘确认信号，下一实际交易日开盘成交。"
          : "日线收盘确认信号，下一实际交易日开盘成交。"}
      </p>

      {isPool && universeInfo?.capped && (
        <p className="mt-2 text-xs text-amber-300/90">
          股票池共 {universeInfo.pool_size} 只，本次按「{universeInfo.sample_label || `代码序前 ${universeInfo.used}`}」取样。
          {universeInfo.sample_fallback === "code_order" ? " 成交额不足，已回退为确定性代码序。" : ""}
          {sector === "watchlist" ? (
            <>
              <Link to="/data#watchlist" className="ml-1 underline hover:text-slate-200">
                编辑自选池
              </Link>
            </>
          ) : (
            " 若要指定标的，请改用自选池或单股回测。"
          )}
        </p>
      )}
      {isPool && sector === "watchlist" && !universeInfo?.capped && (
        <p className="mt-2 text-xs text-slate-500">
          当前使用
          <Link to="/data#watchlist" className="mx-1 underline hover:text-slate-300">
            我的自选池
          </Link>
          。
        </p>
      )}

      {isSingle && strategy === "signal_replay" && (
        <div className="card mt-4">
          <label className="label">信号表（date,side）</label>
          <textarea
            className="input min-h-[120px] w-full font-mono text-xs"
            value={signalText}
            onChange={(e) => setSignalText(e.target.value)}
            placeholder={"date,side\n2024-01-05,buy\n2024-03-01,S"}
          />
          <p className="mt-1 text-xs text-slate-500">每行一条；side 支持 buy/sell、B/S、买入/卖出。无行情的日期会跳过。</p>
        </div>
      )}

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
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="btn-secondary" onClick={() => {
              setTrainBars(barFrequency === "weekly" ? 52 : 252);
              setTestBars(barFrequency === "weekly" ? 13 : 63);
            }}>
              {barFrequency === "weekly" ? "1 年训练 + 1 季测试" : "1 年训练 + 1 季测试"}
            </button>
            <button type="button" className="btn-secondary" onClick={() => {
              setTrainBars(barFrequency === "weekly" ? 104 : 504);
              setTestBars(barFrequency === "weekly" ? 26 : 126);
            }}>
              2 年训练 + 半年测试
            </button>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <label className="label">Train K 线根数（{barFrequency === "weekly" ? "周" : "日"}）</label>
              <input
                className="input w-full"
                type="number"
                min={2}
                value={trainBars}
                onChange={(e) => setTrainBars(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="label">Test K 线根数（{barFrequency === "weekly" ? "周" : "日"}）</label>
              <input
                className="input w-full"
                type="number"
                min={1}
                value={testBars}
                onChange={(e) => setTestBars(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="label">Purge 间隔（{barFrequency === "weekly" ? "周" : "交易日"}）</label>
              <input className="input w-full" type="number" min={0} value={purgeBars} onChange={(e) => setPurgeBars(Number(e.target.value))} />
            </div>
            <div>
              <label className="label">Embargo 间隔（{barFrequency === "weekly" ? "周" : "交易日"}）</label>
              <input className="input w-full" type="number" min={0} value={embargoBars} onChange={(e) => setEmbargoBars(Number(e.target.value))} />
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            当前窗口约为：训练 {barFrequency === "weekly" ? `${Math.round(trainBars / 52 * 10) / 10} 年` : `${Math.round(trainBars / 21)} 个月`}
            {" · "}测试 {barFrequency === "weekly" ? `${Math.round(testBars / 4.33)} 个月` : `${Math.round(testBars / 21)} 个月`}。
            Purge/Embargo 用于隔离训练与测试样本，降低信息泄漏。
          </p>
          <button
            className="btn-secondary mt-3"
            disabled={job.isRunning || submitting}
            onClick={runWalkForward}
          >
            运行 Walk-Forward
          </button>
          {wfResult?.segment_count != null && (
            <div className="mt-2 text-sm text-emerald-400">
              <p>稳健性 {wfResult.stability_score} · {wfResult.segment_count} 段</p>
              <p>
                OOS Sharpe {wfResult.oos_sharpe ?? "—"} · 最大回撤{" "}
                {wfResult.oos_max_drawdown_pct ?? "—"}% · IS/OOS 衰减{" "}
                {wfResult.is_oos_decay_pct ?? "—"}%
              </p>
              <p>参数漂移 {wfResult.parameter_drift?.mean_distance ?? "—"}</p>
            </div>
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
            {isSingle && (
              <SingleStockTradeView
                code={effectiveValidateDetail.codes?.[0] || stockCode}
                trades={effectiveValidateDetail.trades || []}
                tradesTruncated={Boolean(effectiveValidateDetail.trades_truncated)}
                equity={effectiveValidateDetail.equity_curve}
              />
            )}
            {isSingle && Array.isArray(effectiveValidateDetail.skipped_signals) && effectiveValidateDetail.skipped_signals.length > 0 && (
              <p className="mt-2 text-xs text-amber-300/90">
                已跳过 {effectiveValidateDetail.skipped_signals.length} 条无行情/无效信号：
                {effectiveValidateDetail.skipped_signals.map((s: { date?: string }) => s.date).filter(Boolean).join("、")}
              </p>
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
          {isSimple &&
            Array.isArray(effectiveValidateDetail.stock_returns) &&
            effectiveValidateDetail.stock_returns.length > 1 && (
              <StockReturnsTable rows={effectiveValidateDetail.stock_returns} />
            )}
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
