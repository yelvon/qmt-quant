import React from "react";
import PageCallout from "../components/PageCallout";

const sections = [
  {
    title: "数据浏览（② 同步后）",
    body: "在「数据浏览」页可按交易日查看横截面、按代码查看时间序列并绘制日 K 线。策略回测支持把本地日线按实际交易周聚合为周线；周末最后交易日确认信号，下一实际交易日成交。",
  },
  {
    title: "策略回测（③）",
    body: "简单模式一次完成参数扫描与 A 股规则验证并展示净值；研究模式先扫描候选参数，再送到 ④ 做规则验证。内置策略含双均线、MACD 金叉死叉、买入持有与低估值动量。日线与周线周期会随研究记录传递。",
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
    body: "将历史切成多段 train/test：在 train 段选最优参数，在 test 段看样本外收益。可用日线/周线预设，并配置 Purge 与 Embargo 隔离样本，降低信息泄漏。",
  },
  {
    title: "实验中心与因子 IC",
    body: "实验中心统一查看候选扫描、规则验证与 Walk-Forward 记录，可筛选、对比指标变化并继续研究。因子 IC 支持日线/周线和多个未来收益周期；同一因子会按 horizon 分行展示。",
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
