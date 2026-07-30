import React from "react";

type Props = {
  progress: number;
  status?: string;
  message?: string;
};

export default function JobProgressBar({ progress, status, message }: Props) {
  const pct = Math.round(Math.min(1, Math.max(0, progress)) * 100);
  return (
    <div className="mt-3">
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span>{status || "等待中"}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
      {message && <p className="mt-1 text-xs text-slate-500">{message}</p>}
    </div>
  );
}
