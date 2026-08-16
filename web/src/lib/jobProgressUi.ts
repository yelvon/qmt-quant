/** Step definitions and formatting for job progress UI. */

export type JobStepDef = { id: string; label: string };

export const JOB_STEP_DEFS: Record<string, JobStepDef[]> = {
  data_check: [
    { id: "prepare", label: "准备" },
    { id: "coverage", label: "覆盖统计" },
    { id: "stale", label: "滞后扫描" },
    { id: "market", label: "缺日检查" },
    { id: "completeness", label: "完整度" },
    { id: "quality", label: "数据质量" },
    { id: "save", label: "保存结果" },
  ],
  sync_bars: [
    { id: "prepare", label: "准备" },
    { id: "sync", label: "下载入库" },
    { id: "export", label: "导出文件" },
  ],
  sync_financial: [
    { id: "prepare", label: "准备" },
    { id: "sync", label: "拉取财报" },
    { id: "save", label: "写入完成" },
  ],
  sync_repair: [
    { id: "repair", label: "补数修复" },
  ],
  sync_check_repair: [
    { id: "check", label: "检测缺口" },
    { id: "repair", label: "补数修复" },
    { id: "verify", label: "复检" },
    { id: "save", label: "完成" },
  ],
  catalog_export: [{ id: "export", label: "导出 Parquet" }],
  research: [
    { id: "load", label: "加载数据" },
    { id: "scan", label: "策略扫描" },
    { id: "save", label: "保存结果" },
  ],
  walk_forward: [
    { id: "load", label: "加载数据" },
    { id: "segment", label: "分段回测" },
    { id: "save", label: "汇总保存" },
  ],
  validate: [
    { id: "load", label: "加载数据" },
    { id: "backtest", label: "规则回测" },
    { id: "compare", label: "对比结论" },
    { id: "save", label: "保存结果" },
  ],
  backtest: [
    { id: "scan", label: "筛选参数" },
    { id: "backtest", label: "规则回测" },
    { id: "save", label: "保存结果" },
  ],
  screen: [
    { id: "load", label: "加载数据" },
    { id: "scan", label: "逐股筛选" },
    { id: "rank", label: "排序入库" },
  ],
  screen_ic: [
    { id: "load", label: "加载数据" },
    { id: "factors", label: "提取因子" },
    { id: "ic", label: "计算 IC" },
  ],
  pipeline: [
    { id: "sync", label: "更新数据" },
    { id: "catalog", label: "导出文件" },
    { id: "research", label: "快速试策略" },
    { id: "validate", label: "仔细验策略" },
  ],
};

export function formatEtaSeconds(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) return "";
  if (seconds < 60) return `约 ${Math.max(1, seconds)} 秒`;
  if (seconds < 3600) return `约 ${Math.max(1, Math.floor(seconds / 60))} 分钟`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return mins > 0 ? `约 ${hours} 小时 ${mins} 分钟` : `约 ${hours} 小时`;
}

export function stepsForJobType(jobType: string): JobStepDef[] {
  return JOB_STEP_DEFS[jobType] || [];
}

/** Strip internal engine ids from progress messages shown in the UI. */
export function humanizeProgressMessage(message?: string | null): string {
  if (!message) return "";
  let text = message;
  const replacements: [RegExp, string][] = [
    [/custom_validator/gi, "A 股规则引擎"],
    [/vectorbt/gi, "快速扫描"],
    [/nautilus/gi, "高保真引擎"],
    [/运行\s*A 股规则引擎\s*回测/g, "按 A 股规则回测"],
    [/运行\s*高保真引擎\s*回测/g, "按高保真规则回测"],
  ];
  for (const [pattern, repl] of replacements) {
    text = text.replace(pattern, repl);
  }
  return text;
}
