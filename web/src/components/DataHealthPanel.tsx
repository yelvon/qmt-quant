import React from "react";
import { Link } from "react-router-dom";
import JobProgressBar from "./JobProgressBar";
import StatusBadge from "./StatusBadge";
import TechnicalDetails from "./TechnicalDetails";

type Check = {
  name: string;
  ok: boolean;
  coverage?: string;
  detail?: string;
};

type JobProgress = {
  progress: number;
  status: string;
  message: string;
  step?: string;
  detail?: string;
  etaSeconds?: number | null;
  error?: string | null;
  jobType?: string;
};

type Props = {
  check: {
    checks?: Check[];
    bar_coverage_pct?: number;
    bar_date_min?: string | null;
    bar_date_max?: string | null;
    as_of?: string;
    needs_repair?: boolean;
    universe_estimated?: boolean;
    universe_total?: number;
    gap_summary?: { stale_count?: number };
    stale_codes?: string[];
  } | null;
  lastScan?: { as_of?: string; stale_count?: number; needs_repair?: boolean } | null;
  loading?: boolean;
  healthJob?: JobProgress | null;
  repairJob?: JobProgress | null;
  onCheck?: () => void;
  onRepair?: () => void;
  onRepairCancel?: () => void;
  repairCancelling?: boolean;
  repairing?: boolean;
};

export default function DataHealthPanel({
  check,
  lastScan,
  loading,
  healthJob,
  repairJob,
  onCheck,
  onRepair,
  onRepairCancel,
  repairCancelling,
  repairing,
}: Props) {
  const healthRunning =
    healthJob && (healthJob.status === "running" || healthJob.status === "pending");
  const repairRunning =
    repairJob && (repairJob.status === "running" || repairJob.status === "pending");

  if (healthRunning) {
    return (
      <JobProgressBar
        heading="数据健康检查"
        jobType="data_check"
        progress={healthJob.progress}
        status={healthJob.status}
        message={healthJob.message}
        step={healthJob.step}
        detail={healthJob.detail}
        etaSeconds={healthJob.etaSeconds}
        error={healthJob.error}
      />
    );
  }

  if (loading && !check) {
    return <p className="text-sm text-slate-500">正在提交检查任务…</p>;
  }

  if (!check) {
    return (
      <div className="rounded-lg border border-dashed border-slate-800 px-4 py-6 text-center">
        <p className="text-sm text-slate-400">
          数据健康检查会扫描全库覆盖、滞后个股与质量指标，耗时较长。提交后可查看分阶段进度与预计剩余时间。
        </p>
        {lastScan?.as_of && (
          <p className="mt-2 text-xs text-slate-500">
            上次检查：{lastScan.as_of}
            {lastScan.stale_count != null ? ` · 滞后 ${lastScan.stale_count} 只` : ""}
          </p>
        )}
        {onCheck && (
          <button type="button" className="btn-primary mt-4 text-sm" disabled={loading} onClick={onCheck}>
            {loading ? "提交中…" : "开始检查"}
          </button>
        )}
      </div>
    );
  }

  const items = check.checks || [];
  const coreOk = items.slice(0, 4).every((c) => c.ok);
  const staleCount = check.gap_summary?.stale_count ?? 0;
  const barMin = check.bar_date_min;
  const barMax = check.bar_date_max;

  return (
    <div>
      {repairRunning && (
        <div className="mb-4">
          <JobProgressBar
            heading="数据修复"
            jobType={repairJob.jobType || "sync_check_repair"}
            progress={repairJob.progress}
            status={repairJob.status}
            message={repairJob.message}
            step={repairJob.step}
            detail={repairJob.detail}
            etaSeconds={repairJob.etaSeconds}
            error={repairJob.error}
            onCancel={onRepairCancel}
            cancelling={repairCancelling}
          />
        </div>
      )}

      {(barMin || barMax) && (
        <div className="mb-4 rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3">
          <p className="text-sm text-slate-200">本地已同步日线范围</p>
          <p className="mt-1 font-mono text-sm text-emerald-300">
            {barMin && barMax ? `${barMin} ~ ${barMax}` : barMax || barMin || "—"}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            <Link to="/data/browse?tab=cross_section" className="text-emerald-400 hover:underline">
              在数据浏览中查看
            </Link>
            {" · "}
            需要更长历史请使用「全量同步」。
          </p>
        </div>
      )}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-400">
          行情覆盖 {check.universe_estimated ? "—" : `${check.bar_coverage_pct ?? "—"}%`}
          {!check.universe_estimated && check.universe_total
            ? `（${check.universe_total} 只）`
            : ""}
          {staleCount > 0 ? ` · 滞后 ${staleCount} 只` : ""}
          {check.as_of ? ` · 截至 ${check.as_of}` : ""}
        </p>
        <div className="flex items-center gap-2">
          {onCheck && (
            <button
              type="button"
              className="btn-secondary text-xs"
              disabled={loading || repairing}
              onClick={onCheck}
            >
              {loading ? "提交中…" : "重新检查"}
            </button>
          )}
          {check.needs_repair && onRepair && !repairRunning && (
            <button type="button" className="btn-primary text-xs" disabled={repairing} onClick={onRepair}>
              一键修复
            </button>
          )}
          <StatusBadge
            ok={coreOk && !check.needs_repair && !repairRunning}
            label={repairRunning ? "修复中" : coreOk && !check.needs_repair ? "数据就绪" : "需关注"}
          />
        </div>
      </div>
      {check.universe_estimated && (
        <p className="mb-3 text-xs text-amber-300/90">
          股票池规模尚未记录，覆盖率仅供参考。请先完成一次「更新今日数据」。
        </p>
      )}
      <ul className="space-y-2">
        {items.map((c) => (
          <li
            key={c.name}
            className="flex items-start justify-between gap-3 rounded-lg border border-slate-800 px-3 py-2"
          >
            <div>
              <p className="text-sm text-slate-200">{c.name}</p>
              <p className="text-xs text-slate-500">{c.detail}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {c.coverage && c.coverage !== "—" && (
                <span className="text-xs text-slate-500">{c.coverage}</span>
              )}
              <StatusBadge ok={c.ok} label={c.ok ? "OK" : "注意"} />
            </div>
          </li>
        ))}
      </ul>
      <TechnicalDetails data={check} />
    </div>
  );
}
