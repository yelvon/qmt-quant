import React, { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import PageCallout from "../components/PageCallout";

export default function LivePage() {
  const [trade, setTrade] = useState<any>(null);
  const [codes, setCodes] = useState("600519.SH");
  const [dryRun, setDryRun] = useState(true);
  const [orders, setOrders] = useState<any[]>([]);

  useEffect(() => {
    apiGet("/api/trade/status").then(setTrade);
  }, []);

  async function preview() {
    const list = codes.split(",").map((c) => c.trim()).filter(Boolean);
    const res = await apiPost<any[]>("/api/trade/preview", {
      codes: list,
      side: "buy",
      quantity: 100,
    });
    setOrders(res);
  }

  async function submit() {
    const list = codes.split(",").map((c) => c.trim()).filter(Boolean);
    const res = await apiPost<any[]>("/api/trade/submit", {
      codes: list,
      side: "buy",
      quantity: 100,
      live: !dryRun,
    });
    setOrders(res);
    apiGet("/api/trade/status").then(setTrade);
  }

  return (
    <div>
      <PageCallout>实盘默认模拟下单（dry_run）。真实下单需关闭模拟并二次确认。</PageCallout>
      <div className="card space-y-3">
        <p className="text-sm text-slate-400">
          连接：{trade?.connected ? "已连接" : "未连接"} · 模式：{trade?.dry_run ? "模拟" : "实盘"}
        </p>
        <div>
          <label className="label">信号来源（代码，逗号分隔）</label>
          <input className="input" value={codes} onChange={(e) => setCodes(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          模拟下单（推荐）
        </label>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={preview}>
            预览订单
          </button>
          <button className="btn-primary" onClick={submit}>
            提交
          </button>
        </div>
      </div>
      {orders.length > 0 && (
        <div className="card mt-4">
          <pre className="text-xs text-slate-400">{JSON.stringify(orders, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
