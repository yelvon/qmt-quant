import React, { useEffect, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { useJobTracker } from "../lib/useJobTracker";
import PageCallout from "../components/PageCallout";
import JobProgressBar from "../components/JobProgressBar";
import ActionCard from "../components/ActionCard";
import StepProgress from "../components/StepProgress";
import OnboardingChecklist from "../components/OnboardingChecklist";
import StatusBadge from "../components/StatusBadge";
import { jobStatusLabel } from "../lib/errorMessages";

type Action = { id: string; label: string; route: string; reason: string };

export default function DashboardPage() {
  const [status, setStatus] = useState<any>(null);
  const [step, setStep] = useState("");
  const [stepLabel, setStepLabel] = useState("");
  const [hideOnboarding, setHideOnboarding] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  const job = useJobTracker();

  const refresh = () => apiGet("/api/status").then(setStatus);
  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (job.status === "completed") refresh();
  }, [job.status]);

  useEffect(() => {
    if (job.message && job.status === "running") {
      if (job.message.includes("更新数据") || job.message.includes("同步")) {
        setStep("sync");
        setStepLabel(job.message);
      }
    }
  }, [job.message, job.status]);

  async function runPipeline() {
    setPipelineError(null);
    try {
      const res = await apiPost<{ job_id: string }>("/api/jobs/pipeline");
      job.trackJob(res.job_id, "一键跑通：更新数据", "pipeline");
      setStep("sync");
      setStepLabel("更新数据");
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : String(err));
    }
  }

  const actions: Action[] = status?.actions || [];

  return (
    <div>
      {!hideOnboarding && (
        <OnboardingChecklist
          doctorOk={status?.doctor_ok}
          coverage={status?.data_check?.bar_coverage_pct}
          onDismiss={() => setHideOnboarding(true)}
        />
      )}
      <PageCallout>
        今天建议：{status?.suggestion || "加载中…"}。按下方卡片逐步操作，或使用一键跑通。
      </PageCallout>

      {actions.length > 0 && (
        <div className="mb-4 space-y-3">
          {actions.map((a, i) => (
            <ActionCard key={a.id} {...a} primary={i === 0} />
          ))}
        </div>
      )}

      <div className="card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-medium">系统状态</h2>
          <StatusBadge ok={status?.doctor_ok} label={status?.doctor_ok ? "环境 OK" : "待修复"} />
        </div>
        <p className="text-sm text-slate-400">
          行情覆盖 {status?.data_check?.bar_coverage_pct ?? "-"}%
        </p>
        <button className="btn-primary mt-4" disabled={job.isRunning} onClick={runPipeline}>
          一键跑通
        </button>
        {pipelineError && <p className="mt-2 text-sm text-red-300">{pipelineError}</p>}
        {job.jobId && (
          <>
            {stepLabel && <p className="mt-2 text-sm text-slate-400">{stepLabel}</p>}
            <StepProgress currentStep={step} progress={job.progress} />
            <JobProgressBar
              progress={job.progress}
              status={job.status}
              message={job.message}
              error={job.error}
              jobType={job.jobType}
              step={job.step}
              detail={job.detail}
              etaSeconds={job.etaSeconds}
              onCancel={job.isRunning ? () => job.cancelJob() : undefined}
              completeAction={
                job.status === "completed"
                  ? { label: "查看验证结果", to: "/validation" }
                  : undefined
              }
            />
          </>
        )}
      </div>

      <div className="card mt-4">
        <h2 className="mb-2 text-base font-medium">最近任务</h2>
        <ul className="space-y-1 text-sm text-slate-300">
          {(status?.recent_jobs || []).map((j: any) => (
            <li key={j.id} className="flex items-center gap-2">
              <span>{j.display_name}</span>
              <StatusBadge ok={j.status === "completed"} label={jobStatusLabel(j.status)} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
