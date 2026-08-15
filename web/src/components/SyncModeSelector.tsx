import React from "react";
import type { SyncMode } from "../lib/syncPlan";

type Props = {
  mode: SyncMode;
  disabled?: boolean;
  onChange: (mode: SyncMode) => void;
};

function ModeCard({
  active,
  disabled,
  title,
  subtitle,
  onClick,
}: {
  active: boolean;
  disabled?: boolean;
  title: string;
  subtitle: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={
        active
          ? "flex-1 rounded-xl border-2 border-emerald-500 bg-emerald-600/10 p-4 text-left transition"
          : "flex-1 rounded-xl border border-slate-700 bg-slate-950/50 p-4 text-left transition hover:border-slate-600 disabled:opacity-50"
      }
    >
      <div className="flex items-center gap-2">
        <span
          className={
            active
              ? "inline-flex h-4 w-4 items-center justify-center rounded-full border-2 border-emerald-400 bg-emerald-500"
              : "inline-flex h-4 w-4 rounded-full border-2 border-slate-600"
          }
        >
          {active ? <span className="h-1.5 w-1.5 rounded-full bg-white" /> : null}
        </span>
        <span className="text-sm font-medium text-slate-100">{title}</span>
      </div>
      <p className="mt-2 pl-6 text-xs leading-relaxed text-slate-400">{subtitle}</p>
    </button>
  );
}

export default function SyncModeSelector({ mode, disabled, onChange }: Props) {
  return (
    <div>
      <p className="label mb-2">同步方式（二选一）</p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <ModeCard
          active={mode === "incremental"}
          disabled={disabled}
          title="增量更新"
          subtitle="日常维护：只补最近几个交易日"
          onClick={() => onChange("incremental")}
        />
        <ModeCard
          active={mode === "full"}
          disabled={disabled}
          title="全量同步"
          subtitle="首次或换复权：按历史长度重拉整段"
          onClick={() => onChange("full")}
        />
      </div>
    </div>
  );
}
