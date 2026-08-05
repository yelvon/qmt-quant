import React from "react";
import type { ColumnMeta } from "../lib/dataApi";

type Props = {
  columns: ColumnMeta[];
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  pageSize: number;
  loading?: boolean;
  sortCol?: string;
  sortDir?: "asc" | "desc";
  onSort?: (col: string) => void;
  onPageChange?: (page: number) => void;
  onRowClick?: (row: Record<string, unknown>) => void;
};

function formatCell(value: unknown, colId: string): string {
  if (value == null) return "—";
  if (colId === "change_pct" && typeof value === "number") {
    const sign = value >= 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}%`;
  }
  if (typeof value === "number") {
    if (Number.isInteger(value)) return String(value);
    return value.toFixed(4).replace(/\.?0+$/, "");
  }
  return String(value);
}

export default function DataTable({
  columns,
  rows,
  total,
  page,
  pageSize,
  loading,
  sortCol,
  sortDir,
  onSort,
  onPageChange,
  onRowClick,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              {columns.map((c) => (
                <th key={c.id} className="cursor-pointer p-2 whitespace-nowrap" onClick={() => onSort?.(c.id)}>
                  {c.label}
                  {sortCol === c.id ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="p-4 text-center text-slate-500">
                  加载中…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-4 text-center text-slate-500">
                  暂无数据
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr
                  key={i}
                  className={`border-t border-slate-800 ${onRowClick ? "cursor-pointer hover:bg-slate-800/50" : ""}`}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map((c) => (
                    <td
                      key={c.id}
                      className={`p-2 whitespace-nowrap ${
                        c.id === "change_pct" && typeof row[c.id] === "number"
                          ? (row[c.id] as number) >= 0
                            ? "text-red-400"
                            : "text-emerald-400"
                          : ""
                      }`}
                    >
                      {formatCell(row[c.id], c.id)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between text-sm text-slate-400">
        <span>
          共 {total} 条，第 {page}/{totalPages} 页
        </span>
        <div className="space-x-2">
          <button
            type="button"
            className="btn-secondary text-xs"
            disabled={page <= 1}
            onClick={() => onPageChange?.(page - 1)}
          >
            上一页
          </button>
          <button
            type="button"
            className="btn-secondary text-xs"
            disabled={page >= totalPages}
            onClick={() => onPageChange?.(page + 1)}
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}
