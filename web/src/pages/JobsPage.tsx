import React, { useEffect, useState } from "react";
import { apiGet } from "../lib/api";
import PageCallout from "../components/PageCallout";

export default function JobsPage() {
  const [jobs, setJobs] = useState<any[]>([]);

  useEffect(() => {
    apiGet<any[]>("/api/jobs?limit=50").then(setJobs);
  }, []);

  return (
    <div>
      <PageCallout>任务记录：人话任务名与状态，便于追溯同步、回测与选股。</PageCallout>
      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="p-2">任务</th>
              <th>类型</th>
              <th>环境</th>
              <th>状态</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className="border-t border-slate-800">
                <td className="p-2">{j.display_name}</td>
                <td>{j.job_type}</td>
                <td>{j.env}</td>
                <td>{j.status}</td>
                <td className="text-slate-500">{j.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
