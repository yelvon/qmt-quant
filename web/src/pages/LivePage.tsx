import React, { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { fetchKline } from "../lib/dataApi";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import TechnicalDetails from "../components/TechnicalDetails";

type DraftOrder = {
  code: string;
  side: "buy" | "sell";
  quantity: number;
  priceMissing?: boolean;
};

function roundLot(n: number): number {
  if (!Number.isFinite(n) || n < 100) return 100;
  return Math.floor(n / 100) * 100;
}

export default function LivePage() {
  const [trade, setTrade] = useState<any>(null);
  const [drafts, setDrafts] = useState<DraftOrder[]>([{ code: "600519.SH", side: "buy", quantity: 100 }]);
  const [dryRun, setDryRun] = useState(true);
  const [orders, setOrders] = useState<any[]>([]);
  const [screenRuns, setScreenRuns] = useState<{ id: string; label: string }[]>([]);
  const [signalSource, setSignalSource] = useState("manual");
  const [showConfirm, setShowConfirm] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const positions: any[] = trade?.positions || [];
  const posQty = useMemo(() => {
    const map: Record<string, number> = {};
    for (const p of positions) {
      map[String(p.code)] = Number(p.available ?? p.quantity ?? 0);
    }
    return map;
  }, [positions]);

  useEffect(() => {
    apiGet("/api/trade/status").then(setTrade);
    apiGet<any[]>("/api/options/screening-runs").then(setScreenRuns);
  }, []);

  useEffect(() => {
    if (signalSource === "manual") return;
    let cancelled = false;
    (async () => {
      const data = await apiGet<{ codes: string[] }>(`/api/screening/${signalSource}/codes`);
      if (cancelled || !data.codes?.length) return;
      const cash = Number(trade?.portfolio_value || 0);
      const n = data.codes.length;
      const budget = cash > 0 ? cash / n : 0;
      const next: DraftOrder[] = [];
      for (const code of data.codes) {
        let qty = 100;
        let priceMissing = true;
        try {
          const k = await fetchKline({ code, adjust: "front" });
          const last = k.ohlc?.[k.ohlc.length - 1]?.[1];
          if (last && budget > 0) {
            qty = roundLot(budget / last);
            priceMissing = false;
          }
        } catch {
          /* keep default */
        }
        next.push({ code, side: "buy", quantity: qty, priceMissing });
      }
      if (!cancelled) setDrafts(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [signalSource, trade?.portfolio_value]);

  function updateDraft(i: number, patch: Partial<DraftOrder>) {
    setDrafts((rows) => rows.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));
  }

  function addDraft() {
    setDrafts((rows) => [...rows, { code: "", side: "buy", quantity: 100 }]);
  }

  async function preview() {
    setPreviewError(null);
    const payload = {
      orders: drafts.filter((d) => d.code.trim()).map((d) => ({
        code: d.code.trim(),
        side: d.side,
        quantity: d.quantity,
      })),
    };
    try {
      const res = await apiPost<any[]>("/api/trade/preview", payload);
      setOrders(res);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : String(err));
    }
  }

  async function submit(confirmed = false) {
    if (!dryRun && !confirmed) {
      setShowConfirm(true);
      return;
    }
    const payload = {
      orders: drafts.filter((d) => d.code.trim()).map((d) => ({
        code: d.code.trim(),
        side: d.side,
        quantity: d.quantity,
      })),
      live: !dryRun,
      confirm: !dryRun ? "LIVE" : undefined,
    };
    const res = await apiPost<any[]>("/api/trade/submit", payload);
    setOrders(res);
    setShowConfirm(false);
    apiGet("/api/trade/status").then(setTrade);
  }

  return (
    <div>
      <PageCallout>
        实盘默认模拟下单。本页勾选只影响这一次提交，不会改设置里的「默认模拟下单」。真实下单需关闭模拟并二次确认。
      </PageCallout>
      <div className="card space-y-3">
        <p className="text-sm text-slate-400">
          连接：{trade?.connected ? "已连接" : "未连接"} · 账户：{trade?.account_id || "—"} · 资金：
          {trade?.portfolio_value != null ? Number(trade.portfolio_value).toLocaleString() : "—"} · 设置默认：
          {trade?.dry_run ? "模拟" : "实盘"}
        </p>
        {positions.length > 0 && (
          <div className="overflow-x-auto">
            <p className="mb-1 text-sm text-slate-300">持仓</p>
            <table className="w-full text-left text-sm">
              <thead className="text-slate-400">
                <tr>
                  <th className="p-2">代码</th>
                  <th>数量</th>
                  <th>可用</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p: any) => (
                  <tr key={p.code} className="border-t border-slate-800">
                    <td className="p-2">{p.code}</td>
                    <td>{p.quantity ?? "—"}</td>
                    <td>{p.available ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <PresetSelect
          label="信号来源"
          value={signalSource}
          options={[
            { id: "manual", label: "手动输入" },
            ...screenRuns.map((r) => ({ id: r.id, label: r.label })),
          ]}
          onChange={(v) => setSignalSource(v)}
        />
        <div className="space-y-2">
          {drafts.map((d, i) => (
            <div key={`${d.code}-${i}`} className="grid gap-2 md:grid-cols-4">
              <input
                className="input"
                value={d.code}
                onChange={(e) => updateDraft(i, { code: e.target.value })}
                placeholder="代码"
              />
              <select
                className="input"
                value={d.side}
                onChange={(e) => updateDraft(i, { side: e.target.value as "buy" | "sell" })}
              >
                <option value="buy">买入</option>
                <option value="sell">卖出</option>
              </select>
              <input
                className="input"
                type="number"
                step={100}
                min={100}
                value={d.quantity}
                onChange={(e) => updateDraft(i, { quantity: Number(e.target.value) })}
              />
              <p className="self-center text-xs text-slate-500">
                {d.priceMissing ? "未取到价格，手数默认 100" : ""}
                {d.side === "sell" && d.code && posQty[d.code] != null
                  ? ` 可用 ${posQty[d.code]}`
                  : ""}
              </p>
            </div>
          ))}
          <button type="button" className="text-xs text-emerald-400 hover:underline" onClick={addDraft}>
            加一行
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          本次模拟下单（不改全局设置）
        </label>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={preview}>
            预览订单
          </button>
          <button className="btn-primary" onClick={() => submit(false)}>
            提交
          </button>
        </div>
        {previewError && <p className="text-sm text-red-300">{previewError}</p>}
      </div>
      {showConfirm && (
        <div className="card mt-4 border border-amber-600">
          <p className="text-amber-400">确认真实下单？此操作将连接 xttrader 发送委托。</p>
          <div className="mt-3 flex gap-2">
            <button className="btn-primary" onClick={() => submit(true)}>
              确认 LIVE 下单
            </button>
            <button className="btn-secondary" onClick={() => setShowConfirm(false)}>
              取消
            </button>
          </div>
        </div>
      )}
      {orders.length > 0 && (
        <div className="card mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="p-2">代码</th>
                <th>方向</th>
                <th>数量</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o, i) => (
                <tr key={i} className="border-t border-slate-800">
                  <td className="p-2">{o.code || o.symbol || "—"}</td>
                  <td>{o.side || "buy"}</td>
                  <td>{o.quantity ?? o.volume ?? "—"}</td>
                  <td>
                    {o.ok === false
                      ? o.reason || "拒绝"
                      : o.status || (o.dry_run ? "模拟" : "已提交")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <TechnicalDetails data={orders} />
        </div>
      )}
    </div>
  );
}
