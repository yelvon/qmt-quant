/** Job type helpers — align with backend `job.job_type`. */

export type JobType =
  | "sync_bars"
  | "sync_financial"
  | "sync_check_repair"
  | "sync_repair"
  | "catalog_export"
  | "pipeline"
  | string;

export function isBarsSyncJob(jobType: string): boolean {
  return jobType === "sync_bars";
}

export function isFinancialSyncJob(jobType: string): boolean {
  return jobType === "sync_financial";
}

export function isRepairJob(jobType: string): boolean {
  return jobType === "sync_check_repair" || jobType === "sync_repair";
}

export function jobTypeLabel(jobType: string): string {
  switch (jobType) {
    case "sync_bars":
      return "日线同步";
    case "sync_financial":
      return "财报同步";
    case "sync_check_repair":
    case "sync_repair":
      return "数据修复";
    case "catalog_export":
      return "导出验策略";
    case "pipeline":
      return "一键跑通";
    default:
      return "后台任务";
  }
}

export function inferJobTypeFromMessage(message: string): string {
  if (message.includes("财报")) return "sync_financial";
  if (message.includes("修复")) return "sync_check_repair";
  if (message.includes("导出")) return "catalog_export";
  if (message.includes("增量") || message.includes("全量") || message.includes("K 线")) {
    return "sync_bars";
  }
  return "";
}
