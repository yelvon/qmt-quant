import React from "react";
import ReactECharts from "echarts-for-react";

type Props = {
  title?: string;
  categories?: string[];
  values?: number[];
  equity?: number[];
};

export default function EquityChart({ title, categories, values, equity }: Props) {
  const option =
    equity && equity.length
      ? {
          title: { text: title || "净值曲线", textStyle: { color: "#e2e8f0", fontSize: 14 } },
          xAxis: { type: "category", data: equity.map((_, i) => i), axisLabel: { color: "#94a3b8" } },
          yAxis: { type: "value", axisLabel: { color: "#94a3b8" } },
          series: [{ type: "line", data: equity, smooth: true, color: "#10b981" }],
          grid: { left: 40, right: 20, top: 40, bottom: 30 },
        }
      : {
          title: { text: title || "参数热力", textStyle: { color: "#e2e8f0", fontSize: 14 } },
          xAxis: { type: "category", data: categories || [], axisLabel: { color: "#94a3b8", rotate: 45 } },
          yAxis: { type: "value", axisLabel: { color: "#94a3b8" } },
          series: [{ type: "bar", data: values || [], color: "#10b981" }],
          grid: { left: 40, right: 20, top: 40, bottom: 60 },
        };

  return <ReactECharts option={option} style={{ height: 320 }} />;
}
