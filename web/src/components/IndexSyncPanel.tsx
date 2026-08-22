import React from "react";
import { Link } from "react-router-dom";

type Props = {
  incremental: boolean;
  instrumentCount?: number;
  benchmarkCount?: number;
  industryCount?: number;
  dateMin?: string | null;
  dateMax?: string | null;
  hs300Min?: string | null;
  hs300Max?: string | null;
};

function formatRange(min?: string | null, max?: string | null): string {
  if (min && max) return `${min} ~ ${max}`;
  if (max) return `截至 ${max}`;
  if (min) return `自 ${min}`;
  return "暂无";
}

export default function IndexSyncPanel({
  incremental,
  instrumentCount = 0,
  benchmarkCount = 0,
  industryCount = 0,
  dateMin,
  dateMax,
  hs300Min,
  hs300Max,
}: Props) {
  const hasLocal = instrumentCount > 0 || Boolean(dateMin || dateMax);

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-300">
        同步基准指数与申万/迅投一级行业指数，写入独立表（不复权、不混入股票日线）。回测对比沪深300依赖这里的数据。
      </p>
      <ul className="flex flex-wrap gap-2">
        {["上证", "深成", "创业板", "科创50", "上证50", "沪深300", "中证500", "中证1000"].map((label) => (
          <li
            key={label}
            className="rounded-md border border-slate-800 bg-slate-950/50 px-2 py-1 text-xs text-slate-400"
          >
            {label}
          </li>
        ))}
        <li className="rounded-md border border-slate-800 bg-slate-950/50 px-2 py-1 text-xs text-slate-400">
          一级行业（最多约 40 只）
        </li>
      </ul>

      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
        <p className="text-sm font-medium text-slate-200">本次将同步</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-slate-500">模式</p>
            <p className="mt-1 text-sm text-slate-200">
              {incremental ? "增量（已有指数补最近窗口）" : "全量（基准约 20 年，行业约 3 年）"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">覆盖</p>
            <p className="mt-1 text-sm text-slate-200">8 只基准 + 行业指数</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">本地已有</p>
            <p className="mt-1 text-sm text-slate-200">
              {hasLocal
                ? `${instrumentCount} 只（基准 ${benchmarkCount} / 行业 ${industryCount}）· ${formatRange(dateMin, dateMax)}`
                : "暂无指数日线"}
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          沪深300：{hs300Min || hs300Max ? formatRange(hs300Min, hs300Max) : "尚未同步"}
          {" · "}
          核对请到{" "}
          <Link to="/data/browse?table=index_daily_bar&tab=kline" className="text-emerald-400 hover:underline">
            数据浏览 · 指数日线
          </Link>
        </p>
        <p className="mt-2 text-xs text-slate-500">
          首次增量若本地为空，基准仍会拉最长约 20 年。行业板块对不上则只更新基准，不会失败。
        </p>
      </div>
    </div>
  );
}
