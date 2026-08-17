import React, { useEffect, useState } from "react";
import { apiGet, apiPut, setApiToken } from "../lib/api";
import PageCallout from "../components/PageCallout";
import StatusBadge from "../components/StatusBadge";

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>({});
  const [apiToken, setApiTokenInput] = useState("");
  const [saved, setSaved] = useState(false);
  const [doctor, setDoctor] = useState<any>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    apiGet("/api/settings").then(setSettings);
    setApiTokenInput(localStorage.getItem("qmt_api_token") || "");
  }, []);

  async function runDoctor() {
    setChecking(true);
    try {
      const res = await apiGet<any>("/api/doctor");
      setDoctor(res);
    } finally {
      setChecking(false);
    }
  }

  async function save() {
    setApiToken(apiToken.trim() || null);
    await apiPut("/api/settings", {
      qmt_install_dir: settings.qmt?.install_dir,
      qmt_python: settings.python?.qmt_env,
      quant_python: settings.python?.quant_env,
      userdata_path: settings.qmt?.userdata_path,
      account_id: settings.qmt?.account_id,
      dry_run: settings.trade?.dry_run,
      commission_rate: settings.backtest?.commission_rate,
      stamp_tax_rate: settings.backtest?.stamp_tax_rate,
      sync_auto_repair: settings.data?.sync?.auto_repair,
      validation_engine: settings.backtest?.validation_engine,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    await runDoctor();
  }

  function patch(path: string[], value: string | boolean | number) {
    setSettings((s: any) => {
      const next = { ...s };
      let cur = next;
      for (let i = 0; i < path.length - 1; i++) {
        cur[path[i]] = { ...cur[path[i]] };
        cur = cur[path[i]];
      }
      cur[path[path.length - 1]] = value;
      return next;
    });
  }

  return (
    <div>
      <PageCallout>设置页：QMT 路径与 Python 环境只需配置一次，保存后自动检测。</PageCallout>
      <div className="card space-y-4">
        <div>
          <label className="label">QMT 安装目录</label>
          <input
            className="input w-full"
            value={settings.qmt?.install_dir || ""}
            onChange={(e) => patch(["qmt", "install_dir"], e.target.value)}
          />
        </div>
        <div>
          <label className="label">qmt-env Python</label>
          <input
            className="input w-full"
            value={settings.python?.qmt_env || ""}
            onChange={(e) => patch(["python", "qmt_env"], e.target.value)}
          />
        </div>
        <div>
          <label className="label">quant-env Python</label>
          <input
            className="input w-full"
            value={settings.python?.quant_env || ""}
            onChange={(e) => patch(["python", "quant_env"], e.target.value)}
          />
        </div>
        <div>
          <label className="label">xttrader userdata 路径</label>
          <input
            className="input w-full"
            value={settings.qmt?.userdata_path || ""}
            onChange={(e) => patch(["qmt", "userdata_path"], e.target.value)}
          />
        </div>
        <div>
          <label className="label">资金账号</label>
          <input
            className="input w-full"
            value={settings.qmt?.account_id || ""}
            onChange={(e) => patch(["qmt", "account_id"], e.target.value)}
          />
        </div>
        <div>
          <label className="label">API Token（可选，与 settings.yaml 中 web.api_token 一致）</label>
          <input
            className="input w-full"
            type="password"
            autoComplete="off"
            value={apiToken}
            onChange={(e) => setApiTokenInput(e.target.value)}
            placeholder="留空则不发送 Authorization"
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.trade?.dry_run !== false}
            onChange={(e) => patch(["trade", "dry_run"], e.target.checked)}
          />
          默认模拟下单
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.data?.sync?.auto_repair === true}
            onChange={(e) => {
              setSettings((s: any) => ({
                ...s,
                data: {
                  ...s.data,
                  sync: { ...(s.data?.sync || {}), auto_repair: e.target.checked },
                },
              }));
            }}
          />
          增量同步后自动修复数据缺口
        </label>
        <div>
          <label className="label">验证引擎（④ 仔细验策略默认）</label>
          <select
            className="input w-full"
            value={settings.backtest?.validation_engine || "custom"}
            onChange={(e) => patch(["backtest", "validation_engine"], e.target.value)}
          >
            <option value="custom">A 股规则引擎</option>
            <option value="nautilus">高保真引擎（Nautilus MVP）</option>
          </select>
          <p className="mt-1 text-xs text-slate-500">
            默认保持 A 股规则引擎。Nautilus MVP 仅双均线，且只验证组合中第一只标的。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" onClick={save}>
            保存设置
          </button>
          <button type="button" className="btn-secondary" disabled={checking} onClick={runDoctor}>
            {checking ? "检测中…" : "检测环境"}
          </button>
        </div>
        {saved && <p className="text-sm text-emerald-400">已保存</p>}
      </div>
      {doctor && (
        <div className="card mt-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-medium">环境检测</h2>
            <StatusBadge ok={doctor.ok} label={doctor.ok ? "全部通过" : "有问题"} />
          </div>
          <ul className="space-y-2">
            {(doctor.checks || []).map((c: any) => (
              <li key={c.name} className="flex items-start justify-between gap-2 text-sm">
                <span className="text-slate-400">{c.name}</span>
                <span className="text-right text-slate-300">{c.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
