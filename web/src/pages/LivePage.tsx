import React, { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";

export default function LivePage() {
  const [trade, setTrade] = useState<any>(null);
  const [codes, setCodes] = useState("600519.SH");
  const [dryRun, setDryRun] = useState(true);
  const [orders, setOrders] = useState<any[]>([]);
  const [screenRuns, setScreenRuns] = useState<{ id: string; label: string }[]>([]);
  const [signalSource, setSignalSource] = useState("manual");
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    apiGet("/api/trade/status").then(setTrade);
    apiGet<any[]>("/api/options/screening-runs").then(setScreenRuns);
  }, []);

  async function loadScreenCodes(runId: string) {
    const rows = await apiGet<any[]>(`/api/options/screening-runs`);
    const run = rows.find((r) => r.id === runId);
    if (!run) return;
    setSignalSource(runId);
  }

  useEffect(() => {
    if (signalSource === "manual") return;
    apiGet<{ codes: string[] }>(`/api/screening/${signalSource}/codes`).then((data) => {
      if (data.codes?.length) setCodes(data.codes.join(","));
    });
  }, [signalSource]);

  async function preview() {
    const list = codes.split(",").map((c) => c.trim()).filter(Boolean);
    const res = await apiPost<any[]>("/api/trade/preview", {
      codes: list,
      side: "buy",
      quantity: 100,
    });
    setOrders(res);
  }

  async function submit(confirmed = false) {
    if (!dryRun && !confirmed) {
      setShowConfirm(true);
      return;
    }
    const list = codes.split(",").map((c) => c.trim()).filter(Boolean);
    const res = await apiPost<any[]>("/api/trade/submit", {
      codes: list,
      side: "buy",
      quantity: 100,
      live: !dryRun,
      confirm: !dryRun ? "LIVE" : undefined,
    });
    setOrders(res);
    setShowConfirm(false);
    apiGet("/api/trade/status").then(setTrade);
  }

  return (
    <div>
      <PageCallout>实盘默认模拟下单（dry_run）。真实下单需关闭模拟并二次确认。</PageCallout>
      <div className="card space-y-3">
        <p className="text-sm text-slate-400">
          连接：{trade?.connected ? "已连接" : "未连接"} · 模式：{trade?.dry_run ? "模拟" : "实盘"}
        </p>
        <PresetSelect
          label="信号来源"
          value={signalSource}
          options={[
            { id: "manual", label: "手动输入" },
            ...screenRuns.map((r) => ({ id: r.id, label: r.label })),
          ]}
          onChange={(v) => {
            setSignalSource(v);
            if (v !== "manual") loadScreenCodes(v);
          }}
        />
        <div>
          <label className="label">代码（逗号分隔）</label>
          <input className="input w-full" value={codes} onChange={(e) => setCodes(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          模拟下单（推荐）
        </label>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={preview}>
            预览订单
          </button>
          <button className="btn-primary" onClick={() => submit(false)}>
            提交
          </button>
        </div>
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
        <div className="card mt-4">
          <pre className="text-xs text-slate-400">{JSON.stringify(orders, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
