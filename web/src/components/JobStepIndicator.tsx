import React from "react";
import { stepsForJobType, type JobStepDef } from "../lib/jobProgressUi";

type Props = {
  jobType?: string;
  currentStep?: string;
};

function stepState(steps: JobStepDef[], currentStep: string | undefined, index: number): "done" | "active" | "pending" {
  if (!currentStep) return index === 0 ? "active" : "pending";
  const idx = steps.findIndex((s) => s.id === currentStep);
  if (idx < 0) return "pending";
  if (index < idx) return "done";
  if (index === idx) return "active";
  return "pending";
}

export default function JobStepIndicator({ jobType, currentStep }: Props) {
  const steps = stepsForJobType(jobType || "");
  if (steps.length < 2) return null;

  return (
    <ol className="mb-3 flex flex-wrap gap-1.5">
      {steps.map((step, i) => {
        const state = stepState(steps, currentStep, i);
        return (
          <li
            key={step.id}
            className={
              state === "active"
                ? "rounded-full bg-emerald-600 px-2.5 py-0.5 text-xs text-white"
                : state === "done"
                  ? "rounded-full bg-emerald-900/50 px-2.5 py-0.5 text-xs text-emerald-300"
                  : "rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-500"
            }
          >
            {step.label}
          </li>
        );
      })}
    </ol>
  );
}
