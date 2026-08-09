export type HumanError = {
  message: string;
  route?: string;
  routeLabel?: string;
};

const RULES: { match: RegExp; message: string; route?: string; routeLabel?: string }[] = [
  { match: /no_price_data/i, message: "请先同步日线数据", route: "/data", routeLabel: "去准备数据" },
  { match: /xtquant|qmt_python|qmt-env/i, message: "QMT 环境未就绪，请检查 Python 路径", route: "/settings", routeLabel: "去设置" },
  { match: /\[sync\]/i, message: "数据同步失败，请确认 QMT 已登录", route: "/data", routeLabel: "去准备数据" },
  { match: /\[catalog\]/i, message: "验策略文件导出失败", route: "/data", routeLabel: "去准备数据" },
  { match: /\[research\]/i, message: "快速试策略失败，可能缺少行情数据", route: "/research", routeLabel: "去试策略" },
  { match: /\[validate\]/i, message: "仔细验策略失败", route: "/validation", routeLabel: "去验策略" },
  { match: /insufficient_data/i, message: "历史数据不足，请延长同步区间", route: "/data", routeLabel: "去准备数据" },
];

export function humanizeError(raw?: string | null): HumanError {
  if (!raw) return { message: "任务失败，请稍后重试" };
  for (const rule of RULES) {
    if (rule.match.test(raw)) {
      return { message: rule.message, route: rule.route, routeLabel: rule.routeLabel };
    }
  }
  return { message: raw.length > 120 ? `${raw.slice(0, 120)}…` : raw };
}

export function jobStatusLabel(status?: string): string {
  switch (status) {
    case "running":
      return "进行中";
    case "completed":
      return "已完成";
    case "failed":
      return "失败";
    case "cancelled":
      return "已中断";
    case "pending":
      return "等待中";
    default:
      return status || "等待中";
  }
}

export function parseApiError(raw: string): string {
  try {
    const obj = JSON.parse(raw);
    if (obj?.detail) return String(obj.detail);
  } catch {
    /* plain text */
  }
  return raw;
}
