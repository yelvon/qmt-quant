import React from "react";

type Props = {
  incremental: boolean;
  stockCount: number;
  sector: string;
  rowCount?: number;
  codesCount?: number;
  announceMax?: string | null;
};

const FINANCIAL_TABLES = [
  { key: "Pershareindex", label: "每股指标", hint: "PE、ROE 等，选股常用" },
  { key: "Balance", label: "资产负债表" },
  { key: "Income", label: "利润表" },
  { key: "CashFlow", label: "现金流量表" },
];

export default function FinancialSyncPanel({
  incremental,
  stockCount,
  sector,
  rowCount,
  codesCount,
  announceMax,
}: Props) {
  const hasLocal = (rowCount ?? 0) > 0;

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm text-slate-300">
          同步 QMT 财务报表，供选股与因子分析使用（与上方日线 K 线独立）。
        </p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {FINANCIAL_TABLES.map((t) => (
            <li
              key={t.key}
              className="rounded-md border border-slate-800 bg-slate-950/50 px-2 py-1 text-xs text-slate-400"
              title={t.hint}
            >
              {t.label}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
        <p className="text-sm font-medium text-slate-200">本次将同步</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-slate-500">模式</p>
            <p className="mt-1 text-sm text-slate-200">
              {incremental ? "增量（仅补新披露）" : "全量（整池重拉）"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">覆盖</p>
            <p className="mt-1 text-sm text-slate-200">
              {stockCount > 0 ? `${stockCount} 只 · ${sector}` : sector}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">本地已有</p>
            <p className="mt-1 text-sm text-slate-200">
              {hasLocal
                ? `${codesCount ?? "—"} 只 · 最新披露 ${announceMax || "—"}`
                : "暂无财报数据"}
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          可中断 · 断点续传 · 按批约 50 只下载
          {" · "}
          全量加速可在 <code className="text-slate-400">config/settings.yaml</code> 调整{" "}
          <code className="text-slate-400">sync_batch_size</code> 与{" "}
          <code className="text-slate-400">sync.concurrency</code>（默认 1，建议不超过 2）
        </p>
      </div>
    </div>
  );
}
