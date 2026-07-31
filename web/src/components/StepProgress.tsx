import React from "react";

const STEPS = [
  { id: "sync", label: "更新数据" },
  { id: "catalog", label: "导出验策略文件" },
  { id: "research", label: "快速试策略" },
  { id: "validate", label: "仔细验策略" },
];

type Props = {
  currentStep?: string;
  progress?: number;
};

export default function StepProgress({ currentStep, progress = 0 }: Props) {
  const idx = STEPS.findIndex((s) => s.id === currentStep);

  return (
    <div className="mt-3">
      <ol className="flex flex-wrap gap-2 text-xs">
        {STEPS.map((step, i) => {
          const done = idx >= 0 ? i < idx : progress >= (i + 1) * 0.25;
          const active = step.id === currentStep;
          return (
            <li
              key={step.id}
              className={`rounded-full px-2.5 py-1 ${
                active
                  ? "bg-emerald-600 text-white"
                  : done
                    ? "bg-emerald-900/40 text-emerald-300"
                    : "bg-slate-800 text-slate-500"
              }`}
            >
              {step.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
