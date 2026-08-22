/** Job type helpers — align with backend `job.job_type`. */

export type JobType =
  | "sync_bars"
  | "sync_index"
  | "sync_financial"
  | "sync_check_repair"
  | "sync_repair"
  | "catalog_export"
  | "research"
  | "walk_forward"
  | "validate"
  | "screen"
  | "screen_ic"
  | "data_check"
  | "pipeline"
  | string;

export function isBarsSyncJob(jobType: string): boolean {
  return jobType === "sync_bars";
}

export function isIndexSyncJob(jobType: string): boolean {
  return jobType === "sync_index";
}

export function isFinancialSyncJob(jobType: string): boolean {
  return jobType === "sync_financial";
}

export function isDataCheckJob(jobType: string): boolean {
  return jobType === "data_check";
}

export function isRepairJob(jobType: string): boolean {
  return jobType === "sync_check_repair" || jobType === "sync_repair";
}

export function isBacktestJob(jobType: string): boolean {
  return jobType === "backtest";
}

export function isResearchJob(jobType: string): boolean {
  return jobType === "research" || jobType === "walk_forward";
}

export function isValidationJob(jobType: string): boolean {
  return jobType === "validate";
}

export function isScreeningJob(jobType: string): boolean {
  return jobType === "screen";
}

export function isIcJob(jobType: string): boolean {
  return jobType === "screen_ic";
}

export function jobTypeLabel(jobType: string): string {
  switch (jobType) {
    case "sync_bars":
      return "日线同步";
    case "sync_index":
      return "指数同步";
    case "sync_financial":
      return "财报同步";
    case "sync_check_repair":
    case "sync_repair":
      return "数据修复";
    case "catalog_export":
      return "导出验策略";
    case "research":
      return "快速试策略";
    case "backtest":
      return "策略回测";
    case "walk_forward":
      return "Walk-Forward";
    case "validate":
      return "仔细验策略";
    case "screen":
      return "选股";
    case "screen_ic":
      return "因子 IC";
    case "data_check":
      return "数据健康";
    case "pipeline":
      return "一键跑通";
    default:
      return "后台任务";
  }
}

export function inferJobTypeFromMessage(message: string): string {
  if (message.includes("健康") || message.includes("扫描本地")) return "data_check";
  if (message.includes("指数")) return "sync_index";
  if (message.includes("财报")) return "sync_financial";
  if (message.includes("修复")) return "sync_check_repair";
  if (message.includes("导出")) return "catalog_export";
  if (message.includes("Walk-Forward") || message.includes("walk-forward")) return "walk_forward";
  if (message.includes("策略回测")) return "backtest";
  if (message.includes("验证") || message.includes("仔细验")) return "validate";
  if (message.includes("选股")) return "screen";
  if (message.includes("IC") || message.includes("因子")) return "screen_ic";
  if (message.includes("试策略") || message.includes("扫描")) return "research";
  if (message.includes("一键跑通")) return "pipeline";
  if (message.includes("增量") || message.includes("全量") || message.includes("K 线")) {
    return "sync_bars";
  }
  return "";
}

/** Primary page route for following an in-flight job. */
export function jobRouteForType(jobType: string): string {
  switch (jobType) {
    case "sync_bars":
    case "sync_index":
    case "sync_financial":
    case "sync_repair":
    case "sync_check_repair":
    case "catalog_export":
    case "data_check":
      return "/data";
    case "research":
    case "walk_forward":
    case "backtest":
      return "/research";
    case "validate":
      return "/validation";
    case "screen":
      return "/screening";
    case "screen_ic":
      return "/ic";
    case "pipeline":
      return "/";
    default:
      return "/jobs";
  }
}

export function matchesJobType(jobType: string, expected: JobType | JobType[]): boolean {
  const list = Array.isArray(expected) ? expected : [expected];
  return list.includes(jobType);
}
