import React from "react";
import { Link } from "react-router-dom";
import { jobTypeLabel } from "../lib/jobTypes";

export type ResumableJob = {
  job_id: string;
  job_type: string;
  display_name?: string;
  progress_message?: string;
  processed: number;
  total: number;
  remaining: number;
  sector?: string;
  start?: string;
  end?: string;
  mode?: string;
};

type Props = {
  jobs: ResumableJob[];
  resumingId?: string | null;
  onResume: (job: ResumableJob) => void;
};

function describeJob(job: ResumableJob): string {
  const label = jobTypeLabel(job.job_type);
  const range =
    job.start && job.end ? `${job.start} ~ ${job.end}` : job.sector ? String(job.sector) : "";
  const progress = `${job.processed}/${job.total} 只（剩 ${job.remaining}）`;
  return range ? `${label} · ${range} · ${progress}` : `${label} · ${progress}`;
}

export default function ResumableSyncBanner({ jobs, resumingId, onResume }: Props) {
  if (jobs.length === 0) return null;

  return (
    <div className="mb-4 space-y-2">
      {jobs.map((job) => (
        <div
          key={job.job_id}
          className="rounded-xl border border-amber-900/40 bg-amber-950/25 px-4 py-3"
        >
          <p className="text-sm text-amber-100">有未完成的同步可续传</p>
          <p className="mt-1 text-xs text-amber-200/80">{describeJob(job)}</p>
          <p className="mt-2 text-xs text-amber-200/60">
            请点「续传」继续未完成部分；若再点「开始全量/增量同步」会从头重拉（已有入库数据不会重复，但会浪费 QMT 下载时间）。
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-primary text-sm"
              disabled={resumingId === job.job_id}
              onClick={() => onResume(job)}
            >
              {resumingId === job.job_id ? "续传中…" : "续传未完成同步"}
            </button>
            <Link to="/jobs" className="text-xs text-amber-300/90 underline">
              在任务记录中查看
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
}
