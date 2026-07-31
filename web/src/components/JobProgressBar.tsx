import React from "react";
import { Link } from "react-router-dom";
import { humanizeError, jobStatusLabel } from "../lib/errorMessages";

type Props = {
  progress: number;
  status?: string;
  message?: string;
  error?: string | null;
  completeAction?: { label: string; onClick?: () => void; to?: string };
};

export default function JobProgressBar({
  progress,
  status,
  message,
  error,
  completeAction,
}: Props) {
  const pct = Math.round(Math.min(1, Math.max(0, progress)) * 100);
  const human = status === "failed" ? humanizeError(error || message) : null;

  return (
    <div className="mt-3">
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span>{message || jobStatusLabel(status)}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full transition-all ${status === "failed" ? "bg-red-500" : "bg-emerald-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
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
