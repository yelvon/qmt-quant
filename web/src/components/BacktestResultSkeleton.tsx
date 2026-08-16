import React from "react";

type Props = {
  message?: string;
};

/** Placeholder while backtest results are fetched after job completion. */
export default function BacktestResultSkeleton({
  message = "正在整理回测结果…",
}: Props) {
  return (
    <div id="backtest-results" className="mt-4 space-y-4 animate-pulse" aria-busy="true">
      <div className="card space-y-3">
        <div className="h-4 w-32 rounded bg-slate-700" />
        <div className="h-3 w-full max-w-md rounded bg-slate-800" />
        <div className="h-3 w-2/3 max-w-sm rounded bg-slate-800" />
      </div>
      <div className="card">
        <div className="mb-3 h-4 w-24 rounded bg-slate-700" />
        <div className="h-48 rounded-lg bg-slate-800/80" />
      </div>
      <p className="text-center text-sm text-slate-400">{message}</p>
    </div>
  );
}
