import React, { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, useJobProgress } from "../lib/api";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";

export default function ScreeningPage() {
  const [template, setTemplate] = useState("low_pe");
  const [sector, setSector] = useState("沪深A股");
  const [templates, setTemplates] = useState<{ id: string; label: string }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const [results, setResults] = useState<any[]>([]);

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
        setResults((data.result as any).results || []);
      }
    },
    [jobId]
  );
  useJobProgress(onJob);

  async function runScreen() {
    const res = await apiPost<{ job_id: string }>("/api/jobs/screen", {
      template,
      sector,
      top: 30,
    });
    setJobId(res.job_id);
    setResults([]);
  }

  return (
    <div>
      <PageCallout>选股：内置模板 + 下拉条件，结果可桥接到 ③/④ 作为股票池。</PageCallout>
      <div className="card grid gap-3 md:grid-cols-2">
        <PresetSelect label="模板" value={template} options={templates} onChange={setTemplate} />
        <PresetSelect label="范围" value={sector} options={sectors} onChange={setSector} />
      </div>
      <button className="btn-primary mt-4" onClick={runScreen}>
        开始选股
      </button>
      {jobId && <JobProgressBar progress={progress} status={status} />}
      {results.length > 0 && (
        <div className="card mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="p-2">代码</th>
                <th>PE</th>
                <th>ROE</th>
                <th>得分</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.code} className="border-t border-slate-800">
                  <td className="p-2">{r.code}</td>
                  <td>{r.pe}</td>
                  <td>{r.roe}</td>
                  <td>{r.score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
