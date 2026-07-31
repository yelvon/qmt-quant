import React from "react";
import ReactECharts from "echarts-for-react";

type EquityPoint = { date: string; equity: number };

type Props = {
  title?: string;
  categories?: string[];
  values?: number[];
  equity?: number[] | EquityPoint[];
  benchmark?: EquityPoint[];
};

export default function EquityChart({ title, categories, values, equity, benchmark }: Props) {
  let option;
  if (equity && equity.length) {
    const isObj = typeof equity[0] === "object";
    const dates = isObj ? (equity as EquityPoint[]).map((e) => e.date) : (equity as number[]).map((_, i) => String(i));
    const series: any[] = [
      {
        name: "策略",
        type: "line",
        data: isObj ? (equity as EquityPoint[]).map((e) => e.equity) : equity,
        smooth: true,
        color: "#10b981",
      },
    ];
    if (benchmark && benchmark.length) {
      const bmMap = new Map(benchmark.map((b) => [b.date, b.equity]));
      series.push({
        name: "基准",
        type: "line",
        data: dates.map((d) => bmMap.get(d) ?? null),
        smooth: true,
        color: "#64748b",
      });
    }
    option = {
      title: { text: title || "净值曲线", textStyle: { color: "#e2e8f0", fontSize: 14 } },
      legend: { textStyle: { color: "#94a3b8" } },
      xAxis: { type: "category", data: dates, axisLabel: { color: "#94a3b8" } },
      yAxis: { type: "value", axisLabel: { color: "#94a3b8" } },
      series,
      grid: { left: 40, right: 20, top: 40, bottom: 30 },
    };
  } else {
    option = {
      title: { text: title || "参数热力", textStyle: { color: "#e2e8f0", fontSize: 14 } },
      xAxis: { type: "category", data: categories || [], axisLabel: { color: "#94a3b8", rotate: 45 } },
      yAxis: { type: "value", axisLabel: { color: "#94a3b8" } },
      series: [{ type: "bar", data: values || [], color: "#10b981" }],
      grid: { left: 40, right: 20, top: 40, bottom: 60 },
    };
  }

  return <ReactECharts option={option} style={{ height: 320 }} />;
}
