import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { fetchJobRecord, resultFromJobRecord } from "../lib/jobResult";
import { isScreeningJob } from "../lib/jobTypes";
import { useBacktestMode } from "../lib/backtestMode";
import { useJobTracker } from "../lib/useJobTracker";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import JobProgressBar from "../components/JobProgressBar";
import EmptyState from "../components/EmptyState";

type TemplateMeta = { id: string; pe_max: number; roe_min: number; ma_window: number };

const TEMPLATE_DEFAULTS: Record<string, TemplateMeta> = {
  low_pe: { id: "low_pe", pe_max: 30, roe_min: 0.1, ma_window: 60 },
  ma_bull: { id: "ma_bull", pe_max: 100, roe_min: 0.05, ma_window: 20 },
};

export default function ScreeningPage() {
  const nav = useNavigate();
  const job = useJobTracker();
  const { isSimple, isSingle, setMode } = useBacktestMode();
  const screenActive = Boolean(job.jobId) && isScreeningJob(job.jobType);

  const [template, setTemplate] = useState("low_pe");
  const [sector, setSector] = useState("沪深A股");
  const [peMax, setPeMax] = useState(30);
  const [roeMin, setRoeMin] = useState(0.1);
  const [maWindow, setMaWindow] = useState(60);
  const [topN, setTopN] = useState(30);
  const [listDaysLt, setListDaysLt] = useState(120);
  const [excludeSt, setExcludeSt] = useState(true);
  const [rulePath, setRulePath] = useState("");
  const [ruleYaml, setRuleYaml] = useState("");
  const [rulePresets, setRulePresets] = useState<{ id: string; label: string; yaml: string }[]>([]);
  const [templates, setTemplates] = useState<{ id: string; label: string }[]>([]);
  const [sectors, setSectors] = useState<{ id: string; label: string }[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [runId, setRunId] = useState("");
  const [pageError, setPageError] = useState<string | null>(null);

  const showMa = template === "ma_bull";

  useEffect(() => {
    apiGet<any[]>("/api/options/templates").then(setTemplates);
    apiGet<any[]>("/api/options/sectors").then(setSectors);
    apiGet<{ id: string; label: string; yaml: string }[]>("/api/options/rule-presets")
      .then(setRulePresets)
      .catch(() => setRulePresets([]));
  }, []);

  useEffect(() => {
    if (!screenActive || !job.jobId || job.status !== "completed") return;
    let cancelled = false;
    (async () => {
      try {
        const record = await fetchJobRecord(job.jobId);
        const payload = resultFromJobRecord(record);
        if (!payload || cancelled) return;
        setResults((payload.results as any[]) || []);
        setRunId(String(payload.run_id || ""));
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [screenActive, job.jobId, job.status]);

  function applyTemplate(id: string) {
    setTemplate(id);
    const meta = TEMPLATE_DEFAULTS[id];
    if (!meta) return;
    setPeMax(meta.pe_max);
    setRoeMin(meta.roe_min);
    setMaWindow(meta.ma_window);
  }

  async function runScreen() {
    setPageError(null);
    try {
      const res = await apiPost<{ job_id: string }>("/api/jobs/screen", {
        template,
        sector,
        top: topN,
        exclude_st: excludeSt,
        pe_max: peMax,
        roe_min: roeMin,
        ma_window: showMa ? maWindow : undefined,
        list_days_lt: listDaysLt,
        rule_path: rulePath || undefined,
        rule_yaml: !rulePath && ruleYaml.trim() ? ruleYaml : undefined,
      });
      setResults([]);
      setRunId("");
      job.trackJob(res.job_id, "选股任务运行中…", "screen");
    } catch (err) {
      setPageError(err instanceof Error ? err.message : String(err));
    }
  }

  async function sendToResearch() {
    if (!runId) return;
    const res = await apiPost<{ job_id: string }>("/api/jobs/research", {
      strategy: "screening_rebalance",
      screen_run_id: runId,
    });
    job.trackJob(res.job_id, "选股池试策略中…", "research");
    nav("/research");
  }

  async function sendToValidation() {
    if (!runId) return;
    if (isSimple || isSingle) {
      setMode("research");
    }
    const res = await apiPost<{ job_id: string }>("/api/jobs/validate", {
      strategy: "screening_rebalance",
      screen_run_id: runId,
    });
    job.trackJob(res.job_id, "选股池验策略中…", "validate");
    nav("/validation");
  }

  function pickRulePreset(id: string) {
    setRulePath(id);
    const found = rulePresets.find((p) => p.id === id);
    setRuleYaml(found?.yaml || "");
  }

  return (
    <div>
      <PageCallout>选股：可视化条件 + 模板，结果可桥接到 ③/④ 作为股票池。</PageCallout>
      <div className="card grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        <PresetSelect label="模板" value={template} options={templates} onChange={applyTemplate} />
        <PresetSelect label="范围" value={sector} options={sectors} onChange={setSector} />
        <div>
          <label className="label">PE 上限</label>
          <input
            className="input w-full"
            type="number"
            value={peMax}
            onChange={(e) => setPeMax(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="label">ROE 下限</label>
          <input
            className="input w-full"
            type="number"
            step="0.01"
            value={roeMin}
            onChange={(e) => setRoeMin(Number(e.target.value))}
          />
        </div>
        {showMa && (
          <div>
            <label className="label">均线窗口</label>
            <input
              className="input w-full"
              type="number"
              value={maWindow}
              onChange={(e) => setMaWindow(Number(e.target.value))}
            />
          </div>
        )}
        <div>
          <label className="label">Top N</label>
          <input
            className="input w-full"
            type="number"
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="label">最短上市天数</label>
          <input
            className="input w-full"
            type="number"
            value={listDaysLt}
            onChange={(e) => setListDaysLt(Number(e.target.value))}
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={excludeSt} onChange={(e) => setExcludeSt(e.target.checked)} />
          排除 ST
        </label>
      </div>
      <details className="card mt-4">
        <summary className="cursor-pointer font-medium">高级：YAML 规则</summary>
        <div className="mt-3 space-y-3">
          <PresetSelect
            label="规则预设"
            value={rulePath}
            options={[{ id: "", label: "不使用文件（可用下方 YAML）" }, ...rulePresets]}
            onChange={pickRulePreset}
          />
          <div>
            <label className="label">YAML</label>
            <textarea
              className="input min-h-[160px] w-full font-mono text-xs"
              value={ruleYaml}
              onChange={(e) => {
                setRuleYaml(e.target.value);
                if (rulePath) setRulePath("");
              }}
              placeholder="可选：粘贴或编辑规则；解析失败会报 400"
            />
          </div>
        </div>
      </details>
      {pageError && <p className="mt-2 text-sm text-red-300">{pageError}</p>}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn-primary" disabled={job.isRunning} onClick={runScreen}>
          开始选股
        </button>
        <Link
          className="btn-secondary"
          to={`/ic?template=${encodeURIComponent(template)}&sector=${encodeURIComponent(sector)}`}
        >
          计算 IC
        </Link>
      </div>
      {screenActive && (
        <JobProgressBar
          progress={job.progress}
          status={job.status}
          message={job.message}
          error={job.error}
          jobType={job.jobType}
          step={job.step}
          detail={job.detail}
          etaSeconds={job.etaSeconds}
        />
      )}
      {!results.length && !screenActive && (
        <EmptyState title="还没有选股结果" description="选择模板与条件后点击「开始选股」。" />
      )}
      {runId && (
        <div className="mt-4 flex gap-2">
          <button className="btn-secondary" disabled={job.isRunning} onClick={sendToResearch}>
            送到快速试策略
          </button>
          <button className="btn-secondary" disabled={job.isRunning} onClick={sendToValidation}>
            {isSimple || isSingle ? "送到仔细验策略（将切到研究模式）" : "送到仔细验策略"}
          </button>
        </div>
      )}
      {results.length > 0 && (
        <div className="card mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="p-2">代码</th>
                <th>名称</th>
                <th>PE</th>
                <th>ROE</th>
                <th>得分</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.code} className="border-t border-slate-800">
                  <td className="p-2">
                    <Link className="text-emerald-400 hover:underline" to={`/data/browse?tab=kline&code=${encodeURIComponent(r.code)}`}>
                      {r.code}
                    </Link>
                  </td>
                  <td>{r.name || "—"}</td>
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
