import React from "react";
import ReactECharts from "echarts-for-react";
import type { KlinePayload } from "../lib/dataApi";

type Props = {
  data: KlinePayload | null;
  loading?: boolean;
  title?: string;
};

export default function CandlestickChart({ data, loading, title }: Props) {
  if (loading) {
    return <div className="flex h-80 items-center justify-center text-slate-500">加载 K 线…</div>;
  }
  if (!data || data.empty) {
    return (
      <div className="flex h-80 items-center justify-center text-slate-500">
        {data?.hint || "暂无 K 线数据"}
      </div>
    );
  }

  const option = {
    title: {
      text: title || `${data.code} 日 K (${data.adjust})`,
      textStyle: { color: "#e2e8f0", fontSize: 14 },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
    },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [
      { left: 50, right: 20, top: 40, height: "55%" },
      { left: 50, right: 20, top: "72%", height: "18%" },
    ],
    xAxis: [
      {
        type: "category",
        data: data.dates,
        axisLabel: { color: "#94a3b8" },
        gridIndex: 0,
      },
      {
        type: "category",
        data: data.dates,
        axisLabel: { show: false },
        gridIndex: 1,
      },
    ],
    yAxis: [
      { scale: true, axisLabel: { color: "#94a3b8" }, gridIndex: 0 },
      { scale: true, axisLabel: { color: "#94a3b8" }, gridIndex: 1, splitNumber: 2 },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 0, end: 100 },
      { show: true, xAxisIndex: [0, 1], type: "slider", bottom: 0, height: 20 },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: data.ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: "#ef4444",
          color0: "#10b981",
          borderColor: "#ef4444",
          borderColor0: "#10b981",
        },
      },
      {
        name: "成交量",
        type: "bar",
        data: data.volume,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: "#64748b" },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height: 420 }} />;
}
