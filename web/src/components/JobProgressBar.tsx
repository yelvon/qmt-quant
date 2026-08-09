import React from "react";
import { Link } from "react-router-dom";
import { humanizeError, jobStatusLabel } from "../lib/errorMessages";

type Props = {
  progress: number;
  status?: string;
  message?: string;
  error?: string | null;
  completeAction?: { label: string; onClick?: () => void; to?: string };
  onCancel?: () => void;
  onResume?: () => void;
  canResume?: boolean;
  cancelling?: boolean;
  resuming?: boolean;
  etaSeconds?: number | null;
};

export default function JobProgressBar({
  progress,
  status,
  message,
  error,
  completeAction,
  onCancel,
  onResume,
  canResume,
  cancelling,
  resuming,
  etaSeconds,
}: Props) {
  const pct = Math.round(Math.min(1, Math.max(0, progress)) * 100);
  const human = status === "failed" ? humanizeError(error || message) : null;
  const baseLabel = message || jobStatusLabel(status);
  const label =
    cancelling && status === "running"
      ? baseLabel.includes("中断") ? baseLabel : `${baseLabel}（中断中…）`
      : baseLabel;
  const showCancel = status === "running" && onCancel && !cancelling;
  const showResume = (status === "cancelled" && canResume && onResume) || false;

  return (
    <div className="mt-3 lg:col-span-3">
      <div className="mb-1 flex justify-between gap-2 text-xs text-slate-400">
        <span className="min-w-0 flex-1 truncate">{label}</span>
        <span className="shrink-0">{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full transition-all ${
            status === "failed"
              ? "bg-red-500"
              : status === "cancelled"
                ? "bg-amber-500"
                : "bg-emerald-500"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {(showCancel || showResume) && (
        <div className="mt-2 flex flex-wrap gap-2">
          {showCancel && (
            <button
              type="button"
              className="btn-secondary text-sm"
              disabled={cancelling}
              onClick={onCancel}
            >
              中断同步
            </button>
          )}
          {cancelling && status === "running" && (
            <span className="text-xs text-amber-300/90">已发送中断请求…</span>
          )}
          {showResume && (
            <button
              type="button"
              className="btn-primary text-sm"
              disabled={resuming}
              onClick={onResume}
            >
              {resuming ? "续传中…" : "继续同步（断点续传）"}
            </button>
          )}
        </div>
      )}
      {human && status === "failed" && (
        <div className="mt-2 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          <p>{human.message}</p>
          {human.route && (
            <Link to={human.route} className="mt-1 inline-block text-xs text-red-300 underline">
              {human.routeLabel || "去修复"}
            </Link>
          )}
        </div>
      )}
      {status === "cancelled" && message && (
        <p className="mt-2 text-sm text-amber-200/90">{message}</p>
      )}
      {status === "completed" && completeAction && (
        <div className="mt-2">
          {completeAction.to ? (
            <Link to={completeAction.to} className="btn-secondary text-sm">
              {completeAction.label}
            </Link>
          ) : (
            <button type="button" className="btn-secondary text-sm" onClick={completeAction.onClick}>
              {completeAction.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
