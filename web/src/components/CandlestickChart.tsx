import React, { useEffect, useMemo, useRef } from "react";
import ReactECharts from "echarts-for-react";
import type { KlinePayload } from "../lib/dataApi";
import { markLetter, type TradeMark } from "./TradeBlotter";

type Props = {
  data: KlinePayload | null;
  loading?: boolean;
  title?: string;
  marks?: TradeMark[];
  focusDate?: string | null;
};

export default function CandlestickChart({ data, loading, title, marks, focusDate }: Props) {
  const chartRef = useRef<ReactECharts>(null);

  const option = useMemo(() => {
    if (!data || data.empty) return null;
    const markPoints = (marks || [])
      .map((m) => {
        const idx = data.dates.indexOf(m.date);
        if (idx < 0) return null;
        const bar = data.ohlc[idx];
        if (!bar || bar.length < 4) return null;
        const letter = markLetter(m.side);
        if (!letter) return null;
        const isBuy = letter === "B";
        const low = bar[2];
        const high = bar[3];
        const price = Number(m.price) || (isBuy ? low : high);
        return {
          name: letter,
          coord: [m.date, price],
          value: letter,
          symbol: "triangle",
          symbolRotate: isBuy ? 0 : 180,
          symbolSize: 14,
          symbolOffset: isBuy ? [0, 12] : [0, -12],
          itemStyle: { color: isBuy ? "#ef4444" : "#10b981" },
          label: {
            formatter: letter,
            color: "#e2e8f0",
            fontSize: 11,
            fontWeight: 700,
            offset: isBuy ? [0, 14] : [0, -14],
          },
        };
      })
      .filter(Boolean);

    return {
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
          markPoint: markPoints.length ? { data: markPoints } : undefined,
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
  }, [data, marks, title]);

  useEffect(() => {
    if (!focusDate || !data?.dates?.length) return;
    const idx = data.dates.indexOf(focusDate);
    if (idx < 0) return;
    const inst = chartRef.current?.getEchartsInstance();
    if (!inst) return;
    const windowSize = 20;
    const start = Math.max(0, idx - windowSize);
    const end = Math.min(data.dates.length - 1, idx + windowSize);
    inst.dispatchAction({
      type: "dataZoom",
      startValue: data.dates[start],
      endValue: data.dates[end],
    });
  }, [focusDate, data]);

  if (loading) {
    return <div className="flex h-80 items-center justify-center text-slate-500">加载 K 线…</div>;
  }
  if (!data || data.empty || !option) {
    return (
      <div className="flex h-80 items-center justify-center text-slate-500">
        {data?.hint || "暂无 K 线数据"}
      </div>
    );
  }

  return <ReactECharts ref={chartRef} option={option} style={{ height: 420 }} />;
}
