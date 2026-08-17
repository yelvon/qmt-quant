import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import { parseApiError } from "../lib/errorMessages";
import { useJobTracker } from "../lib/useJobTracker";
import {
  inferJobTypeFromMessage,
  isBarsSyncJob,
  isFinancialSyncJob,
  isRepairJob,
} from "../lib/jobTypes";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import DataHealthPanel from "../components/DataHealthPanel";
import SyncModeSelector from "../components/SyncModeSelector";
import SyncPlanPreview from "../components/SyncPlanPreview";
import FinancialSyncPanel from "../components/FinancialSyncPanel";
import WatchlistPanel from "../components/WatchlistPanel";
import ResumableSyncBanner, { type ResumableJob } from "../components/ResumableSyncBanner";
import {
  FULL_SYNC_RANGE_OPTIONS,
  type RangePresetId,
} from "../lib/rangePresets";
import {
  deriveSyncPlan,
  INCREMENTAL_TRADING_DAYS,
  longRangeConfirmMessage,
  needsLongRangeConfirm,
  pickDefaultRangePreset,
  pickDefaultSyncMode,
  QMT_HISTORY_NOTE,
  type SyncMode,
} from "../lib/syncPlan";

const ADJUST_OPTIONS = [
  { id: "front", label: "前复权" },
  { id: "none", label: "不复权" },
  { id: "back", label: "后复权" },
];

function summaryUrl(sector: string, adjust: string, refresh = false) {
  const params = new URLSearchParams({ sector, adjust });
  if (refresh) {
    params.set("refresh", "true");
  }
  return `/api/data/summary?${params.toString()}`;
}

type HealthJobState = {
  progress: number;
  status: string;
  message: string;
  step?: string;
  detail?: string;
  etaSeconds?: number | null;
  error?: string | null;
};

function qmtStatusUrl(sector: string, refresh = false) {
  const params = new URLSearchParams({ sector });
  if (refresh) {
    params.set("refresh", "true");
  }
  return `/api/qmt/status?${params.toString()}`;
}

function formatLocalRange(min?: string | null, max?: string | null): string {
  if (min && max) return `${min} ~ ${max}`;
  if (max) return `截至 ${max}`;
  if (min) return `自 ${min}`;
  return "暂无";
}

function formatFinancialSummary(check: any): string {
  const codes = check?.financial_codes_count;
  const maxDate = check?.financial_announce_max;
  if (!codes && !maxDate) return "暂无";
  if (codes && maxDate) return `${codes} 只 · 最新披露 ${maxDate}`;
  if (codes) return `${codes} 只`;
  return `最新披露 ${maxDate}`;
}

function jobProgressProps(
  job: ReturnType<typeof useJobTracker>,
  extras: {
    cancelling: boolean;
    resuming: boolean;
    onCancel: () => void;
    onResume?: () => void;
  }
) {
  return {
    progress: job.progress,
    status: job.status,
    message: job.message,
    error: job.error,
    jobType: job.jobType,
    step: job.step,
    detail: job.detail,
    canResume: job.canResume,
    cancelling: job.cancelling || extras.cancelling,
    resuming: extras.resuming,
    etaSeconds: job.etaSeconds,
    onCancel: extras.onCancel,
    onResume: extras.onResume,
  };
}

export default function DataPage() {
  const [sector, setSector] = useState("沪深A股");
  const [adjust, setAdjust] = useState("front");
  const [syncMode, setSyncMode] = useState<SyncMode>("incremental");
  const [rangePreset, setRangePreset] = useState<RangePresetId>("5y");
  const [financialFull, setFinancialFull] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [healthCheck, setHealthCheck] = useState<any>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthJob, setHealthJob] = useState<HealthJobState | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const healthJobIdRef = useRef<string | null>(null);
  const lastRepairDoneRef = useRef("");
  const summaryRef = useRef<any>(null);
  summaryRef.current = summary;
  const defaultsAppliedRef = useRef(false);
  const financialSectionRef = useRef<HTMLDivElement>(null);
  const [qmtOk, setQmtOk] = useState<boolean | null>(null);
  const [qmtMessage, setQmtMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [financialError, setFinancialError] = useState<string | null>(null);
  const [activePlanSummary, setActivePlanSummary] = useState<string>("");
  const [resumableJobs, setResumableJobs] = useState<ResumableJob[]>([]);
  const [resumingJobId, setResumingJobId] = useState<string | null>(null);
  const [nameBackfillLoading, setNameBackfillLoading] = useState(false);
  const [nameBackfillMsg, setNameBackfillMsg] = useState<string | null>(null);

  const job = useJobTracker();
  const effectiveJobType = job.jobType || inferJobTypeFromMessage(job.message);

  const stockCount = summary?.universe_total ?? 0;
  const hasLocalBars = Boolean(summary?.bar_date_min || summary?.bar_date_max);
  const hasLocalFinancial = (summary?.financial_row_count ?? 0) > 0;

  const syncPlan = useMemo(
    () =>
      deriveSyncPlan(syncMode, {
        rangePreset,
        stockCount,
        sectorLabel: sector,
      }),
    [syncMode, rangePreset, stockCount, sector]
  );

  const barsJobActive = Boolean(job.jobId) && isBarsSyncJob(effectiveJobType);
  const financialJobActive = Boolean(job.jobId) && isFinancialSyncJob(effectiveJobType);
  const repairJobActive = Boolean(job.jobId) && isRepairJob(effectiveJobType);
  const repairRunning = repairJobActive && (job.status === "running" || job.status === "pending");
  const repairJobProgress = repairRunning
    ? {
        progress: job.progress,
        status: job.status,
        message: job.message,
        step: job.step,
        detail: job.detail,
        etaSeconds: job.etaSeconds,
        error: job.error,
        jobType: effectiveJobType,
      }
    : null;

  const refreshResumable = useCallback(() => {
    return apiGet<ResumableJob[]>("/api/jobs/resumable").then(setResumableJobs).catch(() => {
      setResumableJobs([]);
    });
  }, []);

  useEffect(() => {
    refreshResumable();
  }, [refreshResumable]);

  useEffect(() => {
    if (window.location.hash === "#watchlist") {
      window.setTimeout(() => {
        document.getElementById("watchlist")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, []);

  useEffect(() => {
    if (job.status === "completed" || job.status === "cancelled") {
      refreshResumable();
    }
  }, [job.status, refreshResumable]);

  const resumableBars = resumableJobs.find((j) => j.job_type === "sync_bars");
  const resumableFinancial = resumableJobs.find((j) => j.job_type === "sync_financial");

  const qmtBusy =
    job.isRunning &&
    (isBarsSyncJob(effectiveJobType) ||
      isFinancialSyncJob(effectiveJobType) ||
      isRepairJob(effectiveJobType) ||
      effectiveJobType === "catalog_export");
  const barsBlocked = qmtBusy && !isBarsSyncJob(effectiveJobType);
  const financialBlocked = qmtBusy && !isFinancialSyncJob(effectiveJobType);

  const refreshSummary = useCallback((refresh = false) => {
    if (summaryRef.current === null) {
      setSummaryLoading(true);
    }
    return apiGet(summaryUrl(sector, adjust, refresh))
      .then((data) => {
        setSummary(data);
      })
      .finally(() => {
        setSummaryLoading(false);
      });
  }, [sector, adjust]);

  const applyHealthResult = useCallback((full: any) => {
    setHealthCheck(full);
    setSummary((prev: any) =>
      prev
        ? {
            ...prev,
            last_health_scan: {
              as_of: full.as_of,
              needs_repair: full.needs_repair,
              stale_count: full.gap_summary?.stale_count,
            },
          }
        : prev
    );
  }, []);

  const runHealthCheck = useCallback(async () => {
    setHealthLoading(true);
    setHealthJob(null);
    setHealthError(null);
    try {
      const res = await apiPost<{ job_id: string }>("/api/jobs/data/check", { sector, adjust });
      healthJobIdRef.current = res.job_id;
      setHealthJob({
        progress: 0.05,
        status: "running",
        message: "任务已提交…",
        step: "prepare",
      });
    } catch (err) {
      setHealthError(parseApiError(err instanceof Error ? err.message : String(err)));
      setHealthLoading(false);
      healthJobIdRef.current = null;
    }
  }, [sector, adjust]);

  useJobProgress(
    useCallback(
      (data: Record<string, unknown>) => {
        const id = healthJobIdRef.current;
        if (!id || data.job_id !== id) return;

        const status = String(data.status || "running");
        setHealthJob({
          progress: Number(data.progress ?? 0),
          status,
          message: String(data.message || data.progress_message || "检查中…"),
          step: String(data.step || ""),
          detail: String(data.detail || ""),
          etaSeconds: data.eta_seconds != null ? Number(data.eta_seconds) : null,
          error: data.error ? String(data.error) : null,
        });

        if (status === "completed") {
          const result = data.result as Record<string, unknown> | undefined;
          if (result && typeof result === "object") {
            applyHealthResult(result);
          }
          healthJobIdRef.current = null;
          setHealthLoading(false);
          setHealthJob(null);
          refreshSummary(true);
        } else if (status === "failed" || status === "cancelled") {
          if (status === "failed") {
            setHealthError(String(data.error || data.message || "数据健康检查失败，请稍后重试"));
          }
          healthJobIdRef.current = null;
          setHealthLoading(false);
        }
      },
      [applyHealthResult, refreshSummary]
    )
  );

  const refreshQmt = useCallback(
    (refresh = false) => {
      return apiGet<{ ok: boolean; message: string }>(qmtStatusUrl(sector, refresh)).then((res) => {
        setQmtOk(res.ok);
        setQmtMessage(res.message);
      });
    },
    [sector]
  );

  useEffect(() => {
    apiGet<any[]>("/api/options/sectors").then(setSectors);
    setSummary(null);
    setHealthCheck(null);
    setHealthJob(null);
    healthJobIdRef.current = null;
    setSummaryLoading(true);
    defaultsAppliedRef.current = false;
    refreshSummary();
    refreshQmt();
  }, [sector, adjust, refreshSummary, refreshQmt]);

  useEffect(() => {
    if (!summary || defaultsAppliedRef.current) return;
    defaultsAppliedRef.current = true;
    const hasBars = Boolean(summary.bar_date_min || summary.bar_date_max);
    setSyncMode(pickDefaultSyncMode(hasBars));
    setRangePreset(pickDefaultRangePreset(hasBars));
  }, [summary]);

  useEffect(() => {
    if (job.status === "completed") {
      refreshSummary(true);
      refreshQmt(true);
    }
  }, [job.status, refreshSummary, refreshQmt]);

  useEffect(() => {
    if (job.status !== "completed" || !isRepairJob(effectiveJobType) || !job.jobId) return;
    if (lastRepairDoneRef.current === job.jobId) return;
    lastRepairDoneRef.current = job.jobId;
    if (healthCheck) {
      void runHealthCheck();
    }
  }, [job.status, job.jobId, effectiveJobType, healthCheck, runHealthCheck]);

  useEffect(() => {
    if (financialJobActive && job.isRunning) {
      financialSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [financialJobActive, job.isRunning, job.jobId]);

  async function startJobRequest(
    path: string,
    body: unknown | undefined,
    message: string,
    jobType: string,
    setError: (msg: string | null) => void
  ) {
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiPost<{ job_id: string }>(path, body);
      job.trackJob(res.job_id, message, jobType);
    } catch (err) {
      setError(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setSubmitting(false);
    }
  }

  async function resumeFromJob(target: ResumableJob) {
    setResumingJobId(target.job_id);
    setSubmitError(null);
    setFinancialError(null);
    try {
      const res = await apiPost<{ job_id: string }>(`/api/jobs/${target.job_id}/resume`);
      job.trackJob(res.job_id, "续传同步中…", target.job_type);
      await refreshResumable();
    } catch (err) {
      const msg = parseApiError(err instanceof Error ? err.message : String(err));
      if (target.job_type === "sync_financial") setFinancialError(msg);
      else setSubmitError(msg);
    } finally {
      setResumingJobId(null);
    }
  }

  async function syncBars() {
    if (
      resumableBars &&
      !window.confirm(
        `检测到未完成的日线同步（${resumableBars.processed}/${resumableBars.total} 只已完成）。\n\n确定要重新开始吗？这会从 QMT 重新下载已完成的股票（入库不重复，但耗时更长）。\n\n建议点「取消」后使用上方「续传未完成同步」。`
      )
    ) {
      return;
    }
    if (
      syncMode === "full" &&
      needsLongRangeConfirm(rangePreset) &&
      !window.confirm(longRangeConfirmMessage(rangePreset, syncPlan))
    ) {
      return;
    }

    setActivePlanSummary(`${syncPlan.progressPrefix} · ${syncPlan.start} ~ ${syncPlan.end}`);

    await startJobRequest(
      "/api/jobs/sync/bars",
      {
        sector,
        incremental: syncMode === "incremental",
        days: INCREMENTAL_TRADING_DAYS,
        adjust,
        range_preset: syncMode === "full" ? rangePreset : undefined,
      },
      `${syncPlan.progressPrefix} ${syncPlan.start} ~ ${syncPlan.end}…`,
      "sync_bars",
      setSubmitError
    );
  }

  async function syncFinancial() {
    if (
      resumableFinancial &&
      !window.confirm(
        `检测到未完成的财报同步（${resumableFinancial.processed}/${resumableFinancial.total} 只已完成）。\n\n确定要重新开始吗？建议先使用「续传未完成同步」。`
      )
    ) {
      return;
    }
    const modeLabel = financialFull ? "全量" : "增量";
    await startJobRequest(
      "/api/jobs/sync/financial",
      { sector, incremental: !financialFull },
      `${modeLabel}同步财报（${sector}）…`,
      "sync_financial",
      setFinancialError
    );
  }

  async function exportCatalog() {
    await startJobRequest(
      "/api/jobs/catalog/export",
      undefined,
      "导出验策略文件中…",
      "catalog_export",
      setSubmitError
    );
  }

  async function checkRepair() {
    setMoreOpen(true);
    await startJobRequest(
      "/api/jobs/sync/check-repair",
      { sector, adjust, detailed: true },
      "检查并修复数据中…",
      "sync_check_repair",
      setSubmitError
    );
  }

  async function handleCancel() {
    setCancelling(true);
    setSubmitError(null);
    setFinancialError(null);
    try {
      await job.cancelJob();
    } catch (err) {
      const msg = parseApiError(err instanceof Error ? err.message : String(err));
      if (financialJobActive) setFinancialError(msg);
      else setSubmitError(msg);
    } finally {
      setCancelling(false);
    }
  }

  async function handleResume() {
    setResuming(true);
    setSubmitError(null);
    setFinancialError(null);
    try {
      await job.resumeJob();
      await refreshResumable();
    } catch (err) {
      const msg = parseApiError(err instanceof Error ? err.message : String(err));
      if (financialJobActive) setFinancialError(msg);
      else setSubmitError(msg);
    } finally {
      setResuming(false);
    }
  }

  async function backfillInstrumentNames() {
    setNameBackfillLoading(true);
    setNameBackfillMsg(null);
    try {
      const res = await apiPost<{ updated: number; remaining: number }>(
        `/api/data/backfill-names?limit=300&sector=${encodeURIComponent(sector)}`
      );
      setNameBackfillMsg(`已补全 ${res.updated} 只股票名称，尚有 ${res.remaining} 只待补全（可多次点击）`);
    } catch (err) {
      setNameBackfillMsg(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setNameBackfillLoading(false);
    }
  }

  const progressExtras = {
    cancelling,
    resuming,
    onCancel: handleCancel,
    onResume: job.canResume ? handleResume : undefined,
  };

  const barsSyncDisabled = submitting || qmtBusy || qmtOk === false;
  const financialSyncDisabled = submitting || qmtBusy || qmtOk === false;
  const barsModeLocked = qmtBusy;

  return (
    <div>
      <div className="mb-4 rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className={qmtOk ? "text-emerald-400" : qmtOk === false ? "text-amber-300" : "text-slate-400"}>
            QMT：{qmtOk === null ? "检测中…" : qmtOk ? "已连接" : "未就绪"}
          </span>
          <span className="text-slate-600">·</span>
          <span className="text-slate-300">股票池：{sector}</span>
          <span className="text-slate-600">·</span>
          <span className="text-slate-300">
            本地日线：
            {hasLocalBars ? (
              <Link to="/data/browse?tab=cross_section" className="ml-1 font-mono text-emerald-300 hover:underline">
                {formatLocalRange(summary?.bar_date_min, summary?.bar_date_max)}
              </Link>
            ) : (
              <span className="ml-1 text-slate-500">{summaryLoading ? "加载中…" : "暂无"}</span>
            )}
          </span>
          <span className="text-slate-600">·</span>
          <span className="text-slate-300">
            本地财报：
            <span className={`ml-1 ${hasLocalFinancial ? "text-emerald-300" : "text-slate-500"}`}>
              {summaryLoading ? "加载中…" : formatFinancialSummary(summary)}
            </span>
          </span>
          {summaryLoading && <span className="text-xs text-slate-500">刷新中…</span>}
        </div>
        {qmtOk === false && (
          <p className="mt-2 text-xs text-amber-200/80">
            {qmtMessage} ·{" "}
            <button type="button" className="underline" onClick={() => refreshQmt(true)}>
              重新检测
            </button>
            {" · "}
            <Link to="/settings" className="underline">
              设置
            </Link>
          </p>
        )}
        {qmtOk === true && qmtMessage && (
          <p className="mt-2 text-xs text-slate-500">{qmtMessage}</p>
        )}
      </div>

      <ResumableSyncBanner
        jobs={resumableJobs.filter((j) => !job.isRunning || j.job_id !== job.jobId)}
        resumingId={resumingJobId}
        onResume={resumeFromJob}
      />

      <WatchlistPanel
        onSyncWatchlist={() => {
          setSector("watchlist");
          document.getElementById("data-sync")?.scrollIntoView({ behavior: "smooth", block: "start" });
        }}
      />

      <div id="data-sync" className="card mb-4 scroll-mt-24 space-y-5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-medium text-slate-100">日线 K 线</h2>
          {barsBlocked && (
            <span className="text-xs text-amber-300/90">
              {isFinancialSyncJob(effectiveJobType) ? "财报同步进行中" : "其他任务进行中"}
            </span>
          )}
        </div>

        <div className={barsBlocked ? "pointer-events-none space-y-5 opacity-45" : "space-y-5"}>
          <SyncModeSelector
            mode={syncMode}
            disabled={barsModeLocked}
            onChange={(mode) => {
              if (barsModeLocked) return;
              setSyncMode(mode);
            }}
          />

          {!financialJobActive || !job.isRunning ? (
            <SyncPlanPreview plan={syncPlan} />
          ) : (
            <div className="rounded-xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-3 text-xs text-slate-500">
              财报同步进行中，上方预览为日线计划；请在下方「财报同步」查看进度。
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <PresetSelect label="股票池" value={sector} options={sectors} onChange={setSector} />
            <PresetSelect label="复权" value={adjust} options={ADJUST_OPTIONS} onChange={setAdjust} />
          </div>

          {syncMode === "full" && (
            <div>
              <PresetSelect
                label="历史长度"
                value={rangePreset}
                options={FULL_SYNC_RANGE_OPTIONS}
                onChange={(v) => setRangePreset(v as RangePresetId)}
              />
              <p className="mt-2 text-xs leading-relaxed text-slate-500">{QMT_HISTORY_NOTE}</p>
            </div>
          )}

          <div className="border-t border-slate-800 pt-4">
            <button className="btn-primary w-full sm:w-auto" disabled={barsSyncDisabled} onClick={syncBars}>
              {syncPlan.ctaLabel}
            </button>
            {submitError && <p className="mt-2 text-sm text-red-300">{submitError}</p>}
          </div>
        </div>

        {barsJobActive && (
          <JobProgressBar
            {...jobProgressProps(job, progressExtras)}
            heading="日线同步进度"
            message={job.message || activePlanSummary}
            completeAction={
              job.status === "completed"
                ? { label: "查看已同步数据", to: "/data/browse?tab=cross_section" }
                : undefined
            }
          />
        )}
      </div>

      <div ref={financialSectionRef} className="card mb-4 space-y-5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-medium text-slate-100">财报同步</h2>
          {financialBlocked && (
            <span className="text-xs text-amber-300/90">日线同步进行中</span>
          )}
        </div>

        <div className={financialBlocked ? "pointer-events-none space-y-5 opacity-45" : "space-y-5"}>
          <FinancialSyncPanel
            incremental={!financialFull}
            stockCount={stockCount}
            sector={sector}
            rowCount={summary?.financial_row_count}
            codesCount={summary?.financial_codes_count}
            announceMax={summary?.financial_announce_max}
          />

          <label className="flex items-center gap-2 text-sm text-slate-400">
            <input
              type="checkbox"
              checked={financialFull}
              onChange={(e) => setFinancialFull(e.target.checked)}
              disabled={financialSyncDisabled}
            />
            全量重拉（默认增量，仅拉新披露）
          </label>

          <button
            className="btn-secondary w-full sm:w-auto"
            disabled={financialSyncDisabled}
            onClick={syncFinancial}
          >
            开始{financialFull ? "全量" : "增量"}同步财报
          </button>
          {financialError && <p className="text-sm text-red-300">{financialError}</p>}
        </div>

        {financialJobActive && (
          <JobProgressBar
            {...jobProgressProps(job, progressExtras)}
            heading="财报同步进度"
          />
        )}
      </div>

      <details
        className="card mb-4 rounded-lg border border-slate-800 bg-slate-950/40"
        open={moreOpen || repairJobActive}
        onToggle={(e) => setMoreOpen((e.target as HTMLDetailsElement).open)}
      >
        <summary className="cursor-pointer select-none px-4 py-3 text-sm text-slate-300">
          其他操作
        </summary>
        <div className="space-y-3 border-t border-slate-800 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="btn-secondary"
              disabled={submitting || qmtBusy}
              onClick={exportCatalog}
            >
              导出验策略文件
            </button>
            <button
              className="btn-secondary"
              disabled={submitting || (repairJobActive && job.isRunning)}
              onClick={checkRepair}
            >
              检查并修复
            </button>
            <button
              className="btn-secondary"
              disabled={nameBackfillLoading || qmtOk === false}
              onClick={backfillInstrumentNames}
            >
              {nameBackfillLoading ? "补全名称中…" : "补全股票名称"}
            </button>
          </div>
          {nameBackfillMsg && <p className="text-xs text-slate-400">{nameBackfillMsg}</p>}

          {repairJobActive && (
            <JobProgressBar
              {...jobProgressProps(job, progressExtras)}
              heading="修复进度"
            />
          )}
        </div>
      </details>

      <div className="card mt-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="font-medium">数据健康</h2>
          {healthLoading && !healthJob && (
            <span className="text-xs text-slate-500">提交中…</span>
          )}
        </div>
        <DataHealthPanel
          check={healthCheck}
          lastScan={summary?.last_health_scan}
          loading={healthLoading}
          healthJob={healthJob}
          repairJob={repairJobProgress}
          onCheck={runHealthCheck}
          onRepair={checkRepair}
          onRepairCancel={handleCancel}
          repairCancelling={cancelling && repairRunning}
          repairing={repairRunning}
        />
        {healthError && (
          <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            健康检查失败：{healthError}
            <button type="button" className="ml-2 underline" onClick={runHealthCheck}>
              重试
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
