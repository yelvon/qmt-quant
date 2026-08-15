import {
  FULL_SYNC_RANGE_OPTIONS,
  formatRangeSummary,
  resolveRangePreset,
  todayISO,
  type RangePresetId,
} from "./rangePresets";

export type SyncMode = "incremental" | "full";

export const INCREMENTAL_TRADING_DAYS = 5;

/** QMT 接口层无固定「最长 N 年」限制；实际可拉取深度取决于券商服务器与标的上市日。 */
export const QMT_HISTORY_NOTE =
  "QMT 日线可按 start_time 指定起点；留空则拉到券商可用的最早数据。A 股常见为上市日起或约 10~20+ 年，因券商/个股而异。";

export type SyncPlan = {
  mode: SyncMode;
  start: string;
  end: string;
  rangeLabel: string;
  ctaLabel: string;
  progressPrefix: string;
  etaHint: string;
  stockHint: string;
};

export function deriveIncrementalRange(endDate = todayISO()): { start: string; end: string } {
  const end = endDate;
  const startDate = new Date(`${end}T12:00:00`);
  startDate.setDate(startDate.getDate() - INCREMENTAL_TRADING_DAYS);
  return { start: startDate.toISOString().slice(0, 10), end };
}

function estimateEta(mode: SyncMode, preset: RangePresetId, stockCount: number): string {
  if (mode === "incremental") {
    return stockCount > 3000 ? "约 5~15 分钟" : "约 3~8 分钟";
  }
  const base =
    preset === "1y"
      ? 15
      : preset === "3y"
        ? 35
        : preset === "5y"
          ? 50
          : preset === "10y"
            ? 90
            : preset === "20y" || preset === "all"
              ? 150
              : 40;
  const scale = stockCount > 4000 ? 1.4 : stockCount > 2000 ? 1.1 : 1;
  const mins = Math.round(base * scale);
  if (mins >= 120) return `约 ${Math.round(mins / 60)} 小时`;
  return `约 ${mins} 分钟`;
}

export function deriveSyncPlan(
  mode: SyncMode,
  options: {
    rangePreset?: RangePresetId;
    stockCount?: number;
    sectorLabel?: string;
  } = {}
): SyncPlan {
  const preset = options.rangePreset ?? "3y";
  const stockCount = options.stockCount ?? 0;
  const stockHint =
    stockCount > 0
      ? `${stockCount} 只股票${options.sectorLabel ? ` · ${options.sectorLabel}` : ""}`
      : options.sectorLabel || "按所选股票池";

  if (mode === "incremental") {
    const { start, end } = deriveIncrementalRange();
    return {
      mode,
      start,
      end,
      rangeLabel: `近 ${INCREMENTAL_TRADING_DAYS} 个交易日`,
      ctaLabel: "开始增量同步",
      progressPrefix: "增量同步",
      etaHint: estimateEta(mode, preset, stockCount),
      stockHint,
    };
  }

  const resolved = resolveRangePreset(preset);
  return {
    mode,
    start: resolved.start,
    end: resolved.end,
    rangeLabel: resolved.label,
    ctaLabel: "开始全量同步",
    progressPrefix: "全量同步",
    etaHint: estimateEta(mode, preset, stockCount),
    stockHint,
  };
}

export function needsLongRangeConfirm(preset: RangePresetId): boolean {
  return preset === "10y" || preset === "20y" || preset === "all";
}

export function longRangeConfirmMessage(preset: RangePresetId, plan: SyncPlan): string {
  const label = FULL_SYNC_RANGE_OPTIONS.find((o) => o.id === preset)?.label || preset;
  return `即将全量同步 ${label}（${formatRangeSummary(plan.start, plan.end)}），预计耗时较长。是否继续？`;
}

export function pickDefaultSyncMode(hasLocalBars: boolean): SyncMode {
  return hasLocalBars ? "incremental" : "full";
}

export function pickDefaultRangePreset(hasLocalBars: boolean): RangePresetId {
  return hasLocalBars ? "5y" : "3y";
}
