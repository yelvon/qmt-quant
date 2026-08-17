import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet } from "../lib/api";

type Run = {
  id: string;
  title?: string;
  engine: string;
  run_kind?: string;
  strategy_id: string;
  created_at: string;
  metrics?: Record<string, number | string | null>;
};

type Detail = { run: Run; detail: Record<string, unknown> };

const labels: Record<string, string> = {
  total_return_pct: "总收益",
  annualized_return_pct: "年化收益",
  max_drawdown_pct: "最大回撤",
  max_drawdown_duration_days: "回撤持续",
  annualized_volatility_pct: "年化波动",
  sharpe: "Sharpe",
  sortino: "Sortino",
  calmar: "Calmar",
  benchmark_excess_return_pct: "基准超额",
  information_ratio: "信息比率",
  turnover: "换手",
  fee_ratio_pct: "费用占比",
  win_rate_pct: "胜率",
  profit_loss_ratio: "盈亏比",
  concentration: "集中度",
};

function Metrics({ run }: { run: Run }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {Object.entries(labels).map(([key, label]) => {
        const value = run.metrics?.[key];
        return (
          <div key={key} className="rounded border border-slate-800 bg-slate-900 p-3">
            <div className="text-xs text-slate-500">{label}</div>
            <div className="mt-1 font-mono">{value == null ? "—" : typeof value === "number" ? value.toFixed(3) : value}</div>
          </div>
        );
      })}
    </div>
  );
}

export default function ExperimentsPage() {
  const { runId } = useParams();
  const [items, setItems] = useState<Run[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [comparison, setComparison] = useState<{ left: Detail; right: Detail } | null>(null);
  const [runKind, setRunKind] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    apiGet<{ items: Run[] }>(`/api/experiments?limit=100${runKind ? `&run_kind=${encodeURIComponent(runKind)}` : ""}`)
      .then((r) => setItems(r.items))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [runKind]);
  useEffect(() => {
    if (runId) {
      setLoading(true);
      setError(null);
      apiGet<Detail>(`/api/experiments/${runId}`)
        .then(setDetail)
        .catch((err) => setError(err instanceof Error ? err.message : String(err)))
        .finally(() => setLoading(false));
    }
    else setDetail(null);
  }, [runId]);

  async function compare() {
    if (!left || !right || left === right) return;
    setError(null);
    try {
      setComparison(await apiGet<{ left: Detail; right: Detail }>(`/api/experiments/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function Diagnostics({ value }: { value: Record<string, unknown> }) {
    const entries = Object.entries(value || {});
    if (!entries.length) return <p className="text-sm text-slate-500">暂无诊断数据</p>;
    return <dl className="grid gap-2 sm:grid-cols-2">{entries.map(([key, item]) => (
      <div key={key} className="rounded border border-slate-800 bg-slate-950/50 p-3">
        <dt className="text-xs text-slate-500">{key.replace(/_/g, " ")}</dt>
        <dd className="mt-1 break-words text-sm text-slate-200">{typeof item === "object" ? JSON.stringify(item) : String(item ?? "—")}</dd>
      </div>
    ))}</dl>;
  }

  if (detail) {
    const diagnostics = detail.detail.diagnostics as Record<string, unknown> | undefined;
    return (
      <section className="space-y-5">
        <Link to="/experiments" className="text-sm text-emerald-400">← 返回实验列表</Link>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold">{detail.run.title || detail.run.id}</h2>
            <span className={`rounded px-2 py-0.5 text-xs ${detail.run.run_kind === "scan" ? "bg-amber-900 text-amber-200" : "bg-emerald-900 text-emerald-200"}`}>
              {detail.run.run_kind === "scan" ? "候选" : "结论"}
            </span>
          </div>
          <p className="text-sm text-slate-500">{detail.run.engine} · {detail.run.strategy_id}</p>
        </div>
        <Metrics run={detail.run} />
        <div className="rounded border border-slate-800 p-4">
          <h3 className="mb-2 font-medium">组合诊断</h3>
          <Diagnostics value={diagnostics || {}} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="btn-secondary" to="/research">用此方向继续研究</Link>
          <Link className="btn-primary" to="/validation">进入规则验证</Link>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">实验中心</h2>
        <p className="text-sm text-slate-500">扫描结果仅作为候选；统一内核或 OOS 验证结果才作为结论。</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-slate-400">类型</span>
        {[["", "全部"], ["scan", "候选扫描"], ["validation", "验证结论"], ["walk_forward", "Walk-Forward"]].map(([id, label]) => (
          <button key={id} className={runKind === id ? "btn-primary" : "btn-secondary"} onClick={() => setRunKind(id)}>{label}</button>
        ))}
        <Link className="btn-secondary ml-auto" to="/research">新建研究</Link>
        <Link className="btn-secondary" to="/validation">新建验证</Link>
      </div>
      {error && <div className="rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}
      <div className="flex flex-wrap gap-2 rounded border border-slate-800 p-4">
        {[left, right].map((value, index) => (
          <select key={index} value={value} onChange={(e) => index ? setRight(e.target.value) : setLeft(e.target.value)} className="rounded bg-slate-900 px-3 py-2">
            <option value="">选择实验 {index + 1}</option>
            {items.map((r) => <option key={r.id} value={r.id}>{r.run_kind === "scan" ? "[候选]" : "[结论]"} {r.title || r.id}</option>)}
          </select>
        ))}
        <button onClick={compare} className="rounded bg-emerald-600 px-4 py-2 text-white">对比</button>
      </div>
      {comparison && (
        <div className="space-y-3">
          <div className="grid gap-4 lg:grid-cols-2">
            <div><h3 className="mb-2">{comparison.left.run.title}</h3><Metrics run={comparison.left.run} /></div>
            <div><h3 className="mb-2">{comparison.right.run.title}</h3><Metrics run={comparison.right.run} /></div>
          </div>
          <div className="rounded border border-slate-800 p-4">
            <h3 className="mb-2 font-medium">右侧相对左侧变化</h3>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(labels).map(([key, label]) => {
                const a = comparison.left.run.metrics?.[key];
                const b = comparison.right.run.metrics?.[key];
                const delta = typeof a === "number" && typeof b === "number" ? b - a : null;
                return <div key={key} className="rounded bg-slate-900 p-2 text-sm"><span className="text-slate-500">{label}</span><span className={`ml-2 font-mono ${delta != null && delta >= 0 ? "text-emerald-400" : "text-amber-300"}`}>{delta == null ? "—" : `${delta >= 0 ? "+" : ""}${delta.toFixed(3)}`}</span></div>;
              })}
            </div>
          </div>
        </div>
      )}
      <div className="space-y-2">
        {loading && <p className="text-sm text-slate-500">正在加载实验记录…</p>}
        {!loading && !error && items.length === 0 && <p className="rounded border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">当前筛选下暂无实验。可从策略回测或验证页开始。</p>}
        {items.map((run) => (
          <Link key={run.id} to={`/experiments/${run.id}`} className="flex items-center justify-between rounded border border-slate-800 p-3 hover:bg-slate-900">
            <span>{run.title || run.id}<span className="ml-2 text-xs text-slate-500">{run.engine}</span></span>
            <span className={run.run_kind === "scan" ? "text-amber-400" : "text-emerald-400"}>{run.run_kind === "scan" ? "候选" : "结论"}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
