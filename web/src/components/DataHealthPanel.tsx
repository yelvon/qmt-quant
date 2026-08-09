import React from "react";
import StatusBadge from "./StatusBadge";
import TechnicalDetails from "./TechnicalDetails";

type Check = {
  name: string;
  ok: boolean;
  coverage?: string;
  detail?: string;
};

type Props = {
  check: {
    checks?: Check[];
    bar_coverage_pct?: number;
    as_of?: string;
    needs_repair?: boolean;
    universe_estimated?: boolean;
    universe_total?: number;
    gap_summary?: { stale_count?: number };
    stale_codes?: string[];
  } | null;
  onRepair?: () => void;
  repairing?: boolean;
};

export default function DataHealthPanel({ check, onRepair, repairing }: Props) {
  if (!check) {
    return <p className="text-sm text-slate-500">加载中…</p>;
  }

  const items = check.checks || [];
  const coreOk = items.slice(0, 4).every((c) => c.ok);
  const staleCount = check.gap_summary?.stale_count ?? 0;

  return (
    <div>
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
          {check.needs_repair && onRepair && (
            <button type="button" className="btn-primary text-xs" disabled={repairing} onClick={onRepair}>
              {repairing ? "修复中…" : "一键修复"}
            </button>
          )}
          <StatusBadge
            ok={coreOk && !check.needs_repair}
            label={coreOk && !check.needs_repair ? "数据就绪" : "需关注"}
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
