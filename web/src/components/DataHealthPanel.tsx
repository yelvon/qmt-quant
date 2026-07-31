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
  } | null;
};

export default function DataHealthPanel({ check }: Props) {
  if (!check) {
    return <p className="text-sm text-slate-500">加载中…</p>;
  }

  const items = check.checks || [];

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm text-slate-400">
          行情覆盖 {check.bar_coverage_pct ?? "—"}%
          {check.as_of ? ` · 截至 ${check.as_of}` : ""}
        </p>
        <StatusBadge ok={items.every((c) => c.ok)} label={items.every((c) => c.ok) ? "数据就绪" : "需关注"} />
      </div>
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
