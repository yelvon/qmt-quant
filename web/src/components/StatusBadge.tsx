import React from "react";

type Props = {
  ok: boolean;
  label?: string;
};

export default function StatusBadge({ ok, label }: Props) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
        ok ? "bg-emerald-900/50 text-emerald-300" : "bg-amber-900/50 text-amber-300"
      }`}
    >
      {label || (ok ? "正常" : "待处理")}
    </span>
  );
}
