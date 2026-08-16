import React, { useMemo, useState } from "react";

export type StockReturnRow = {
  code: string;
  name?: string;
  total_return_pct: number;
  max_drawdown_pct: number;
  trade_count: number;
};

type SortKey = "total_return_pct" | "max_drawdown_pct" | "trade_count" | "code";

type Props = {
  rows: StockReturnRow[];
  className?: string;
};

function returnColor(pct: number) {
  if (pct > 0) return "text-emerald-400";
  if (pct < 0) return "text-red-400";
  return "text-slate-300";
}

export default function StockReturnsTable({ rows, className = "" }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("total_return_pct");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      const na = Number(av);
      const nb = Number(bv);
      return sortDir === "asc" ? na - nb : nb - na;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir(key === "code" ? "asc" : "desc");
  }

  const winners = rows.filter((r) => r.total_return_pct > 0).length;
  const losers = rows.filter((r) => r.total_return_pct < 0).length;

  function header(label: string, key: SortKey) {
    const active = sortKey === key;
    return (
      <th
        key={key}
        className="cursor-pointer pb-2 pr-4 text-xs font-normal text-slate-500 hover:text-slate-300"
        onClick={() => toggleSort(key)}
      >
        {label}
        {active ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
      </th>
    );
  }

  return (
    <div className={`card ${className}`.trim()}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-slate-200">逐股收益</p>
        <p className="text-xs text-slate-500">
          共 {rows.length} 只 · 盈利 {winners} · 亏损 {losers}
        </p>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        每只股票独立账户、满仓运行同一策略参数，便于对比个股表现；与上方组合净值（多股共享资金池）口径不同。
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              {header("代码", "code")}
              <th className="pb-2 pr-4 text-xs font-normal text-slate-500">名称</th>
              {header("收益", "total_return_pct")}
              {header("回撤", "max_drawdown_pct")}
              {header("成交", "trade_count")}
            </tr>
          </thead>
          <tbody className="text-slate-300">
            {sorted.map((row) => (
              <tr key={row.code} className="border-t border-slate-800">
                <td className="py-2 pr-4 font-mono text-xs">{row.code}</td>
                <td className="py-2 pr-4 text-xs text-slate-400">{row.name || "—"}</td>
                <td className={`py-2 pr-4 tabular-nums ${returnColor(row.total_return_pct)}`}>
                  {row.total_return_pct > 0 ? "+" : ""}
                  {row.total_return_pct}%
                </td>
                <td className="py-2 pr-4 tabular-nums text-slate-400">{row.max_drawdown_pct}%</td>
                <td className="py-2 tabular-nums text-slate-400">{row.trade_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
