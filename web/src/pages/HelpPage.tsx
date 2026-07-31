import React from "react";
import PageCallout from "../components/PageCallout";

const sections = [
  {
    title: "VectorBT 快速试策略（③）",
    body: "用 VectorBT 在日线数据上做参数扫描和热力图，快速找到较优的均线组合。结果仅供参考，不能代替真实成交规则验证。",
  },
  {
    title: "自研验证器 / Nautilus（④）",
    body: "仔细验策略使用 AShareDailyBacktester（T+1、涨跌停、费率、滑点）或可选 NautilusTrader 引擎。与 VectorBT 结果对比，判断策略是否值得继续。",
  },
  {
    title: "双 Python 环境",
    body: "qmt-env（QMT 自带 Python）负责 xtquant 数据同步；quant-env（Python 3.12+）负责回测、选股、Web。jobs.force_subprocess_for_qmt 默认 true，确保 QMT 任务在正确环境执行。",
  },
  {
    title: "Walk-Forward 稳健性",
    body: "将历史切成多段 train/test：在 train 段选最优参数，在 test 段看样本外收益。stability_score 表示 OOS 正收益段占比，越高越稳健。",
  },
];

export default function HelpPage() {
  return (
    <div>
      <PageCallout>白话说明各模块用途，详细步骤见 docs/windows-e2e.md。</PageCallout>
      <div className="space-y-4">
        {sections.map((s) => (
          <div key={s.title} className="card">
            <h2 className="mb-2 font-medium text-emerald-400">{s.title}</h2>
            <p className="text-sm text-slate-300">{s.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
