import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import DataTable from "../components/DataTable";
import CandlestickChart from "../components/CandlestickChart";
import {
  fetchDataQuery,
  fetchDateRange,
  fetchKline,
  fetchTableMeta,
  type KlinePayload,
  type QueryResult,
  type TableMeta,
} from "../lib/dataApi";

type TabId = "cross_section" | "series" | "kline";

const ADJUST_FALLBACK = [
  { id: "front", label: "前复权" },
  { id: "none", label: "不复权" },
  { id: "back", label: "后复权" },
];

export default function DataBrowsePage() {
  const [tab, setTab] = useState<TabId>("cross_section");
  const [meta, setMeta] = useState<TableMeta | null>(null);
  const [adjust, setAdjust] = useState("front");
  const [date, setDate] = useState("");
  const [code, setCode] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [codeFilter, setCodeFilter] = useState("");
  const [query, setQuery] = useState<QueryResult | null>(null);
  const [kline, setKline] = useState<KlinePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [klineLoading, setKlineLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [sortCol, setSortCol] = useState("code");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    fetchTableMeta("daily_bar").then((m) => {
      setMeta(m);
      if (m.available_adjust_types?.length && !m.available_adjust_types.includes(adjust)) {
        setAdjust(m.available_adjust_types[0]);
      }
    });
  }, []);

  useEffect(() => {
    fetchDateRange(adjust).then((r) => {
      if (r.max_date) setDate((d) => d || r.max_date!);
      if (r.min_date) setDateFrom((d) => d || r.min_date!);
      if (r.max_date) setDateTo((d) => d || r.max_date!);
    });
  }, [adjust]);

  const loadCrossSection = useCallback(async () => {
    if (!date) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDataQuery({
        table: "daily_bar",
        view_mode: "cross_section",
        date,
        adjust,
        code: codeFilter || undefined,
        page,
        page_size: 100,
        sort_col: sortCol,
        sort_dir: sortDir,
      });
      setQuery({
        ...res,
        columns: res.columns?.length ? res.columns : meta?.columns || [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setQuery(null);
    } finally {
      setLoading(false);
    }
  }, [date, adjust, codeFilter, page, sortCol, sortDir, meta?.columns]);

  const loadSeries = useCallback(async () => {
    if (!code) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDataQuery({
        table: "daily_bar",
        view_mode: "series",
        code,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        adjust,
        page,
        page_size: 100,
        sort_col: sortCol || "date",
        sort_dir: sortDir,
      });
      setQuery({
        ...res,
        columns: res.columns?.length ? res.columns : meta?.columns || [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setQuery(null);
    } finally {
      setLoading(false);
    }
  }, [code, dateFrom, dateTo, adjust, page, sortCol, sortDir, meta?.columns]);

  const loadKline = useCallback(async () => {
    if (!code) return;
    setKlineLoading(true);
    try {
      const res = await fetchKline({
        code,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        adjust,
      });
      setKline(res);
    } finally {
      setKlineLoading(false);
    }
  }, [code, dateFrom, dateTo, adjust]);

  useEffect(() => {
    if (tab === "cross_section") loadCrossSection();
  }, [tab, loadCrossSection]);

  useEffect(() => {
    if (tab === "series") {
      loadSeries();
      loadKline();
    }
  }, [tab, loadSeries, loadKline]);

  useEffect(() => {
    if (tab === "kline") loadKline();
  }, [tab, loadKline]);

  function handleSort(col: string) {
    if (sortCol === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
    setPage(1);
  }

  function openKlineFromRow(row: Record<string, unknown>) {
    const c = String(row.code || "");
    if (!c) return;
    setCode(c);
    setTab("kline");
  }

  const adjustOptions =
    meta?.adjust_options?.filter(
      (o) => !meta.available_adjust_types?.length || meta.available_adjust_types.includes(o.id)
    ) || ADJUST_FALLBACK;

  const tabs: { id: TabId; label: string }[] = [
    { id: "cross_section", label: "横截面" },
    { id: "series", label: "时间序列" },
    { id: "kline", label: "K 线" },
  ];

  return (
    <div>
      <PageCallout>
        浏览已同步的日线与证券列表。若无数据请先在{" "}
        <Link to="/data" className="text-emerald-400 hover:underline">
          ② 准备数据
        </Link>{" "}
        同步。
      </PageCallout>

      <div className="mb-4 flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "btn-primary" : "btn-secondary"}
            onClick={() => {
              setTab(t.id);
              setPage(1);
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="card mb-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <PresetSelect label="复权" value={adjust} options={adjustOptions} onChange={setAdjust} />

        {tab === "cross_section" && (
          <>
            <label className="block text-sm">
              <span className="text-slate-400">交易日</span>
              <input
                type="date"
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5"
                value={date}
                onChange={(e) => {
                  setDate(e.target.value);
                  setPage(1);
                }}
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-400">代码前缀（可选）</span>
              <input
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5"
                placeholder="600519"
                value={codeFilter}
                onChange={(e) => {
                  setCodeFilter(e.target.value);
                  setPage(1);
                }}
              />
            </label>
            <div className="flex items-end">
              <button type="button" className="btn-primary" onClick={loadCrossSection}>
                查询
              </button>
            </div>
          </>
        )}

        {(tab === "series" || tab === "kline") && (
          <>
            <label className="block text-sm">
              <span className="text-slate-400">代码</span>
              <input
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5"
                placeholder="600519.SH"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-400">起始日</span>
              <input
                type="date"
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-slate-400">截止日</span>
              <input
                type="date"
                className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </label>
            <div className="flex items-end gap-2">
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  if (tab === "series") {
                    loadSeries();
                    loadKline();
                  } else {
                    loadKline();
                  }
                }}
              >
                查询
              </button>
            </div>
          </>
        )}
      </div>

      {(tab === "cross_section" || tab === "series") && (
        <div className="card">
          {error && <p className="mb-3 text-sm text-red-300">{error}</p>}
          {query ? (
            <DataTable
              columns={query.columns}
              rows={query.rows}
              total={query.total}
              page={query.page}
              pageSize={query.page_size}
              loading={loading}
              sortCol={sortCol}
              sortDir={sortDir}
              onSort={handleSort}
              onPageChange={setPage}
              onRowClick={tab === "cross_section" ? openKlineFromRow : undefined}
            />
          ) : (
            <p className="text-sm text-slate-500">
              {loading ? "加载中…" : "请选择条件后查询"}
            </p>
          )}
        </div>
      )}

      {(tab === "series" || tab === "kline") && (
        <div className="card mt-4">
          <CandlestickChart data={kline} loading={klineLoading} />
        </div>
      )}
    </div>
  );
}
