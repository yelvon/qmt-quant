import React from "react";
import { Link } from "react-router-dom";

type Comparison = {
  research_return_pct?: number | null;
  validation_return_pct?: number;
  delta_pct?: number | null;
  verdict?: string;
};

type Props = {
  comparison?: Comparison;
  verdict?: string;
  totalReturnPct?: number;
};

function verdictColor(v: string) {
  if (v === "可以采用") return "text-emerald-400";
  if (v === "不建议") return "text-red-400";
  return "text-amber-400";
}

export default function ComparisonCard({ comparison, verdict, totalReturnPct }: Props) {
  const v = verdict || comparison?.verdict || "—";
  const research = comparison?.research_return_pct;
  const validation = comparison?.validation_return_pct ?? totalReturnPct;
  const delta = comparison?.delta_pct;

  return (
    <div className="card">
      <p className={`text-lg font-medium ${verdictColor(v)}`}>结论：{v}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">③ 快速试</p>
          <p className="text-xl font-semibold text-slate-200">
            {research != null ? `${research}%` : "—"}
          </p>
        </div>
        <div className="rounded-lg bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">④ 仔细验</p>
          <p className="text-xl font-semibold text-emerald-400">
            {validation != null ? `${validation}%` : "—"}
          </p>
        </div>
        <div className="rounded-lg bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">差异</p>
          <p className="text-xl font-semibold text-slate-200">
            {delta != null ? `${delta > 0 ? "+" : ""}${delta}%` : "—"}
          </p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {v === "可以采用" && (
          <Link to="/live" className="btn-primary">
            去模拟下单
          </Link>
        )}
        {(v === "建议复核" || v === "不建议") && (
          <Link to="/research" className="btn-secondary">
            回到③调整参数
          </Link>
        )}
      </div>
    </div>
  );
}
