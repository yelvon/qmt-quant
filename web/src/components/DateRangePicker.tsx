import React from "react";
import { rangeForPreset, todayISO, type DatePresetId } from "../lib/dateUtils";

type Preset = { id: DatePresetId; label: string };

const PRESETS: Preset[] = [
  { id: "1m", label: "近 1 月" },
  { id: "3m", label: "近 3 月" },
  { id: "6m", label: "近 6 月" },
  { id: "1y", label: "近 1 年" },
  { id: "all", label: "全部" },
];

type Props = {
  from: string;
  to: string;
  min?: string | null;
  max?: string | null;
  activePreset?: DatePresetId | null;
  loading?: boolean;
  onChange: (from: string, to: string, preset?: DatePresetId | null) => void;
};

export default function DateRangePicker({
  from,
  to,
  min,
  max,
  activePreset = null,
  loading = false,
  onChange,
}: Props) {
  const endCap = max || todayISO();

  function applyPreset(preset: DatePresetId) {
    const next = rangeForPreset(preset, endCap, min);
    onChange(next.from, next.to, preset);
  }

  return (
    <div className="lg:col-span-2">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="label mb-0">日期范围</span>
        {loading && <span className="text-xs text-slate-500">加载可用日期…</span>}
      </div>
      <div className="mb-3 flex flex-wrap gap-2">
        {PRESETS.map((preset) => {
          const selected = activePreset === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              className={
                selected
                  ? "rounded-full border border-emerald-500 bg-emerald-600/20 px-3 py-1 text-xs font-medium text-emerald-300"
                  : "rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs text-slate-200 hover:border-emerald-600 hover:text-emerald-300"
              }
              onClick={() => applyPreset(preset.id)}
            >
              {preset.label}
            </button>
          );
        })}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="label">起始日</span>
          <input
            type="date"
            className="input"
            value={from}
            min={min || undefined}
            max={to || endCap}
            disabled={loading}
            onChange={(e) => onChange(e.target.value, to, null)}
          />
        </label>
        <label className="block text-sm">
          <span className="label">截止日</span>
          <input
            type="date"
            className="input"
            value={to}
            min={from || min || undefined}
            max={endCap}
            disabled={loading}
            onChange={(e) => onChange(from, e.target.value, null)}
          />
        </label>
      </div>
      {from && to && (
        <p className="mt-2 text-xs text-slate-500">
          已选 {from} 至 {to}
          {!max && "（库中暂无行情，将按所选日期查询）"}
        </p>
      )}
    </div>
  );
}
