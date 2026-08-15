import React from "react";
import type { SyncPlan } from "../lib/syncPlan";
import { formatRangeSummary } from "../lib/rangePresets";

type Props = {
  plan: SyncPlan;
};

export default function SyncPlanPreview({ plan }: Props) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
      <p className="text-sm font-medium text-slate-200">本次将同步</p>
      <div className="mt-3 grid gap-4 sm:grid-cols-3">
        <div>
          <p className="text-xs text-slate-500">日期范围</p>
          <p className="mt-1 font-mono text-sm text-emerald-300">
            {formatRangeSummary(plan.start, plan.end)}
          </p>
          <p className="mt-1 text-xs text-slate-500">{plan.rangeLabel}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">覆盖</p>
          <p className="mt-1 text-sm text-slate-200">{plan.stockHint}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">预计耗时</p>
          <p className="mt-1 text-sm text-slate-200">{plan.etaHint}</p>
          <p className="mt-1 text-xs text-slate-500">可中断 · 断点续传</p>
          <p className="mt-1 text-xs text-slate-600">
            全量可在 settings.yaml 调大 sync_batch_size / sync.concurrency（并发默认 1）
          </p>
        </div>
      </div>
    </div>
  );
}
