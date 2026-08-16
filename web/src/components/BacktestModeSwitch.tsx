import React from "react";
import { useBacktestMode, type BacktestMode } from "../lib/backtestMode";
import { useJobTracker } from "../lib/JobProvider";

const OPTIONS: { id: BacktestMode; title: string; hint: string }[] = [
  {
    id: "simple",
    title: "简单回测",
    hint: "整池一键回测，直接看净值曲线",
  },
  {
    id: "single",
    title: "单股回测",
    hint: "指定一只股票，看策略表现与成交",
  },
  {
    id: "research",
    title: "研究扫描",
    hint: "整池参数扫描 + 分步验证",
  },
];

export default function BacktestModeSwitch({ className = "" }: { className?: string }) {
  const { mode, setMode } = useBacktestMode();
  const job = useJobTracker();
  const disabled = job.isRunning;

  return (
    <div className={`card ${className}`.trim()}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-slate-200">回测模式</p>
        {disabled && (
          <span className="text-xs text-amber-300/90">任务运行中，完成后可切换</span>
        )}
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        {OPTIONS.map((opt) => {
          const active = mode === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              disabled={disabled}
              onClick={() => setMode(opt.id)}
              className={`rounded-lg border px-3 py-2 text-left transition disabled:cursor-not-allowed disabled:opacity-50 ${
                active
                  ? "border-emerald-500 bg-emerald-950/40 ring-1 ring-emerald-500/50"
                  : "border-slate-700 bg-slate-900/50 hover:border-slate-600"
              }`}
            >
              <span className={`text-sm font-medium ${active ? "text-emerald-300" : "text-slate-200"}`}>
                {opt.title}
              </span>
              <span className="mt-0.5 block text-xs text-slate-400">{opt.hint}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
