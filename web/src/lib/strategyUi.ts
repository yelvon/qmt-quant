/** Strategy-specific copy and form visibility for research / validation pages. */

export const STRATEGY_HINTS: Record<string, string> = {
  ma_cross: "扫描多组短/长均线组合；柱状图越高表示该参数组合历史收益越好。",
  macd_cross: "扫描 MACD 快/慢/信号线参数；DIF 上穿 DEA（金叉）持有，下穿（死叉）空仓。",
  buy_hold: "等权买入持有基准，用于对比策略是否跑赢简单持有。",
  pe_momentum: "低 PE + 正动量因子策略；需要先在「② 准备数据」同步财报。",
  screening_rebalance: "对选股池等权再平衡；请从「⑤ 选股」送入股票池后再扫描。",
  signal_replay: "粘贴买卖日期表，按 A 股规则（T+1、整手、涨跌停、费用）回放成交。仅单股。",
};

export function usesMaPresets(strategy: string): boolean {
  return strategy === "ma_cross";
}

export function researchCallout(strategy: string): string {
  const hint = STRATEGY_HINTS[strategy] || STRATEGY_HINTS.ma_cross;
  return `研究扫描：${hint} 满意后可送到 ④ 仔细验。`;
}

export function simpleBacktestCallout(strategy: string): string {
  if (strategy === "pe_momentum") {
    return "简单回测：选策略和区间，点一次「运行回测」即可看到净值曲线与指标。需先在 ② 同步财报。";
  }
  if (strategy === "screening_rebalance") {
    return "简单回测：请先从 ⑤ 选股送入股票池。系统会自动筛选较优参数并完成 A 股规则验证。";
  }
  return "简单回测：选股票池、策略和区间，点一次「运行回测」。后台自动筛选较优参数并完成 A 股规则验证，直接看净值曲线。";
}

export function singleBacktestCallout(strategy: string): string {
  if (strategy === "screening_rebalance") {
    return "单股回测不支持「选股再平衡」策略，请换双均线、MACD、买入持有或低估值动量。";
  }
  if (strategy === "pe_momentum") {
    return "单股回测：选定一只股票，检验策略在该股上的历史表现。需先在 ② 同步该股日线与财报。";
  }
  if (strategy === "signal_replay") {
    return "单股回测：粘贴 CSV（date,side），side 可为 buy/sell 或 B/S。无 K 线的信号日会跳过并列出。";
  }
  return "单股回测：搜索并选定一只股票，点「运行回测」。可查看净值曲线、相对沪深300表现及买卖成交明细。";
}

export function strategyAllowedInSingleMode(strategy: string): boolean {
  return strategy !== "screening_rebalance";
}

export function strategyAllowedInPoolMode(strategy: string): boolean {
  return strategy !== "signal_replay";
}

export type PastRunOption = { id: string; label: string; created_at?: string };

/** Human-readable label for past run dropdowns. */
export function formatPastRunLabel(run: PastRunOption): string {
  const raw = String(run.created_at || "");
  const date = raw.includes("T") ? raw.slice(0, 16).replace("T", " ") : raw.slice(0, 10);
  if (date) return `${date} · ${run.label}`;
  return run.label;
}

export function skippedSignalsNote(
  skipped: Array<{ date?: string; code?: string; reason?: string }> | undefined,
  tradeCount?: number,
): string | null {
  const rows = Array.isArray(skipped) ? skipped : [];
  const lotFails = rows.filter((row) => row.reason === "insufficient_cash_for_lot").length;
  if (lotFails > 0) {
    return `有 ${lotFails} 次买入信号因现金不够买 1 手被跳过（高价股在组合默认 10% 仓位下常见）。单股回测会用全部资金下单。`;
  }
  if ((tradeCount ?? 0) === 0 && rows.length === 0) {
    return "区间内没有成交：可能没有金叉/死叉，或信号被停牌、涨跌停挡住。";
  }
  if (rows.length === 0) return null;
  const dates = rows.map((row) => row.date).filter(Boolean).slice(0, 8).join("、");
  const extra = rows.length > 8 ? ` 等 ${rows.length} 条` : "";
  return `已跳过 ${rows.length} 条信号（无行情/无效/停牌等）：${dates}${extra}`;
}

export function payloadErrorMessage(payload: Record<string, unknown>): string | null {
  if (payload.error) {
    const code = String(payload.error);
    if (code === "no_price_data") return "缺少行情数据，请先在「② 准备数据」同步日线。";
    if (code === "insufficient_data") return "历史数据不足，请延长同步区间或换更短回测区间。";
    if (code === "no_screen_codes") return "选股池为空或行情未覆盖，请先完成选股与数据同步。";
    if (code === "research_save_failed") return "参数扫描完成但未能保存，请重试或查看任务记录。";
    if (code === "signal_replay_single_only") return "信号回放只支持一只股票，请切到单股模式并选定标的。";
    if (code === "signal_replay_use_backtest") return "信号回放请用单股「运行回测」，不要走参数扫描。";
    return String(payload.message || code);
  }
  return null;
}
