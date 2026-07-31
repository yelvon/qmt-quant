import React from "react";
import { Link } from "react-router-dom";

const ONBOARDING_KEY = "qmt_quant_onboarding_dismissed";

type Step = {
  id: string;
  label: string;
  route: string;
  done: boolean;
};

type Props = {
  doctorOk?: boolean;
  coverage?: number;
  onDismiss?: () => void;
};

export function isOnboardingDismissed(): boolean {
  return localStorage.getItem(ONBOARDING_KEY) === "1";
}

export function dismissOnboarding(): void {
  localStorage.setItem(ONBOARDING_KEY, "1");
}

export default function OnboardingChecklist({ doctorOk, coverage = 0, onDismiss }: Props) {
  const steps: Step[] = [
    { id: "env", label: "配置 QMT 与 Python 环境", route: "/settings", done: !!doctorOk },
    { id: "data", label: "同步近 3 年日线数据", route: "/data", done: coverage > 80 },
    { id: "research", label: "试默认双均线策略", route: "/research", done: false },
  ];
  const allDone = steps.every((s) => s.done);

  if (isOnboardingDismissed() || allDone) return null;

  return (
    <div className="card mb-4 border border-slate-700">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-medium">首次使用引导</h2>
        <button
          type="button"
          className="text-xs text-slate-500 hover:text-slate-300"
          onClick={() => {
            dismissOnboarding();
            onDismiss?.();
          }}
        >
          不再显示
        </button>
      </div>
      <ol className="space-y-2">
        {steps.map((step, i) => (
          <li key={step.id} className="flex items-center gap-3 text-sm">
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs ${
                step.done ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400"
              }`}
            >
              {step.done ? "✓" : i + 1}
            </span>
            <span className={step.done ? "text-slate-500 line-through" : "text-slate-300"}>
              {step.label}
            </span>
            {!step.done && (
              <Link to={step.route} className="ml-auto text-xs text-emerald-400 hover:underline">
                前往
              </Link>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
