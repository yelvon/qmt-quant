import React, { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";

export default function IcPage() {
  const [template, setTemplate] = useState("low_pe");
  const [sector, setSector] = useState("沪深A股");
  const [templates, setTemplates] = useState<{ id: string; label: string }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    apiGet<any[]>("/api/options/templates").then(setTemplates);
    apiGet<any[]>("/api/options/sectors").then(setSectors);
  }, []);

  const onJob = useCallback(
    (data: Record<string, unknown>) => {
      if (data.job_id !== jobId) return;
      setProgress(Number(data.progress || 0));
      setStatus(String(data.status || ""));
      if (data.status === "completed" && data.result) {
        setResult(data.result);
      }
    },
    [jobId]
  );
  useJobProgress(onJob);

  async function runIc() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/screen/ic", {
      template,
      sector,
    });
    setJobId(res.job_id);
    setResult(null);
  }

  return (
    <div>
      <PageCallout>因子 IC：衡量选股因子与未来收益的相关性，IC 越高说明因子越有效。</PageCallout>
      <div className="card grid gap-3 md:grid-cols-2">
        <PresetSelect label="模板" value={template} options={templates} onChange={setTemplate} />
        <PresetSelect label="范围" value={sector} options={sectors} onChange={setSector} />
      </div>
      <button className="btn-primary mt-4" onClick={runIc}>
        计算 IC
      </button>
      {jobId && <JobProgressBar progress={progress} status={status} />}
      {result && (
        <div className="card mt-4">
          <h2 className="mb-2 font-medium">IC 结果</h2>
          <pre className="overflow-auto text-xs text-slate-400">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
