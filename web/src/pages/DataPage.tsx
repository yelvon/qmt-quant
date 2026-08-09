import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { parseApiError } from "../lib/errorMessages";
import { useJobTracker } from "../lib/useJobTracker";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import DataHealthPanel from "../components/DataHealthPanel";

const ADJUST_OPTIONS = [
  { id: "front", label: "前复权" },
  { id: "none", label: "不复权" },
  { id: "back", label: "后复权" },
];

const RANGE_OPTIONS = [
  { id: "", label: "增量（近5日）" },
  { id: "1y", label: "全量 1 年" },
  { id: "3y", label: "全量 3 年" },
  { id: "5y", label: "全量 5 年" },
];

function checkUrl(sector: string, adjust: string) {
  return `/api/data/check?detailed=true&sector=${encodeURIComponent(sector)}&adjust=${encodeURIComponent(adjust)}`;
}

export default function DataPage() {
  const [sector, setSector] = useState("沪深A股");
  const [adjust, setAdjust] = useState("front");
  const [rangePreset, setRangePreset] = useState("");
  const [financialFull, setFinancialFull] = useState(false);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [check, setCheck] = useState<any>(null);
  const [qmtOk, setQmtOk] = useState<boolean | null>(null);
  const [qmtMessage, setQmtMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [jobKind, setJobKind] = useState<"sync" | "repair" | "other">("sync");

  const job = useJobTracker();

  const refreshCheck = useCallback(() => {
    return apiGet(checkUrl(sector, adjust)).then(setCheck);
  }, [sector, adjust]);

  const refreshQmt = useCallback(() => {
    return apiGet<{ ok: boolean; message: string }>(
      `/api/qmt/status?sector=${encodeURIComponent(sector)}`
    ).then((res) => {
      setQmtOk(res.ok);
      setQmtMessage(res.message);
    });
  }, [sector]);

  useEffect(() => {
    apiGet<any[]>("/api/options/sectors").then(setSectors);
    refreshCheck();
    refreshQmt();
  }, [refreshCheck, refreshQmt]);

  useEffect(() => {
    if (job.status === "completed") {
      refreshCheck();
      refreshQmt();
    }
  }, [job.status, refreshCheck, refreshQmt]);

  async function startJobRequest(
    path: string,
    body?: unknown,
    message = "同步任务已启动…",
    kind: "sync" | "repair" | "other" = "sync"
  ) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await apiPost<{ job_id: string }>(path, body);
      setJobKind(kind);
      job.trackJob(res.job_id, message);
    } catch (err) {
      setSubmitError(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setSubmitting(false);
    }
  }

  async function syncBars(incremental: boolean) {
    await startJobRequest(
      "/api/jobs/sync/bars",
      {
        sector,
        incremental,
        days: 5,
        adjust,
        range_preset: incremental ? undefined : rangePreset || undefined,
      },
      incremental ? "增量同步中…" : "全量同步中…"
    );
  }

  async function syncFinancial() {
    await startJobRequest(
      "/api/jobs/sync/financial",
      { sector, incremental: !financialFull },
      "同步财报中…"
    );
  }

  async function exportCatalog() {
    await startJobRequest("/api/jobs/catalog/export", undefined, "导出验策略文件中…", "other");
  }

  async function checkRepair() {
    await startJobRequest(
      "/api/jobs/sync/check-repair",
      { sector, adjust, detailed: true },
      "检查并修复数据中…",
      "repair"
    );
  }

  async function handleCancel() {
    setCancelling(true);
    setSubmitError(null);
    try {
      await job.cancelJob();
    } catch (err) {
      setSubmitError(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setCancelling(false);
    }
  }

  async function handleResume() {
    setResuming(true);
    setSubmitError(null);
    try {
      await job.resumeJob();
    } catch (err) {
      setSubmitError(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setResuming(false);
    }
  }

  const syncDisabled = submitting || job.isRunning || qmtOk === false;

  return (
    <div>
      <PageCallout>
        Primary =「更新今日数据」（近 5 日增量）。若健康检查提示缺口，使用「一键修复」定向补洞。
        同步前会自动检查 QMT 连接；进行中可「中断同步」，之后可「断点续传」。
      </PageCallout>
      {qmtOk === false && (
        <div className="mb-4 rounded-lg border border-amber-900/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-100">
          <p className="font-medium">QMT 未就绪，无法开始同步</p>
          <p className="mt-1 text-amber-200/80">{qmtMessage}</p>
          <p className="mt-2 text-xs text-amber-200/70">
            请确认 MiniQMT 已登录后，
            <button type="button" className="underline" onClick={() => refreshQmt()}>
              重新检测
            </button>
            ，或前往 <Link to="/settings" className="underline">设置</Link> 检查 Python 路径。
          </p>
        </div>
      )}
      {qmtOk === true && (
        <p className="mb-4 text-xs text-emerald-400/90">{qmtMessage}</p>
      )}
      <p className="mb-4 text-sm text-slate-400">
        <Link to="/data/browse" className="text-emerald-400 hover:underline">
          查看已同步数据 →
        </Link>
      </p>
      <div className="card grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <PresetSelect label="股票池" value={sector} options={sectors} onChange={setSector} />
        <PresetSelect label="复权" value={adjust} options={ADJUST_OPTIONS} onChange={setAdjust} />
        <PresetSelect label="历史长度" value={rangePreset} options={RANGE_OPTIONS} onChange={setRangePreset} />
        <div className="flex flex-wrap items-end gap-2 lg:col-span-3">
          <button className="btn-primary" disabled={syncDisabled} onClick={() => syncBars(true)}>
            更新今日数据
          </button>
          <button className="btn-secondary" disabled={syncDisabled} onClick={() => syncBars(false)}>
            全量同步
          </button>
          <button className="btn-secondary" disabled={syncDisabled} onClick={syncFinancial}>
            同步财报{financialFull ? "（全量）" : "（增量）"}
          </button>
          <button
            className="btn-secondary"
            disabled={submitting || job.isRunning}
            onClick={exportCatalog}
          >
            导出验策略文件
          </button>
        </div>
        {submitError && (
          <p className="text-sm text-red-300 lg:col-span-3">{submitError}</p>
        )}
        <label className="flex items-center gap-2 text-sm text-slate-400 lg:col-span-3">
          <input
            type="checkbox"
            checked={financialFull}
            onChange={(e) => setFinancialFull(e.target.checked)}
          />
          财报全量重拉（默认增量，仅拉新披露）
        </label>
        {job.jobId && (
          <JobProgressBar
            progress={job.progress}
            status={job.status}
            message={job.message}
            error={job.error}
            canResume={job.canResume}
            cancelling={job.cancelling || cancelling}
            resuming={resuming}
            etaSeconds={job.etaSeconds}
            onCancel={handleCancel}
            onResume={handleResume}
            completeAction={job.status === "completed" ? { label: "去试策略", to: "/research" } : undefined}
          />
        )}
      </div>
      <div className="card mt-4">
        <h2 className="mb-3 font-medium">数据健康</h2>
        <DataHealthPanel
          check={check}
          onRepair={checkRepair}
          repairing={jobKind === "repair" && job.isRunning}
        />
      </div>
    </div>
  );
}
