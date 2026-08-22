import React, { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import PageCallout from "../components/PageCallout";
import PresetSelect from "../components/PresetSelect";
import DataTable from "../components/DataTable";
import CandlestickChart from "../components/CandlestickChart";
import DateRangePicker from "../components/DateRangePicker";
import StockSearchInput from "../components/StockSearchInput";
import {
  fetchDataQuery,
  fetchDateRange,
  fetchIndexInstruments,
  fetchKline,
  fetchTableMeta,
  type IndexInstrument,
  type KlinePayload,
  type QueryResult,
  type TableMeta,
} from "../lib/dataApi";
import { defaultOneYearRange, rangeForPreset, todayISO, type DatePresetId } from "../lib/dateUtils";

type TabId = "cross_section" | "series" | "kline";
type SourceId = "daily_bar" | "index_daily_bar";

const ADJUST_FALLBACK = [
  { id: "front", label: "前复权" },
  { id: "none", label: "不复权" },
  { id: "back", label: "后复权" },
];

export default function DataBrowsePage() {
  const [params] = useSearchParams();
  const tabParam = params.get("tab");
  const tableParam = params.get("table") || "";
  const codeParam = params.get("code") || "";
  const initialTab: TabId =
    tabParam === "cross_section" || tabParam === "series" || tabParam === "kline"
      ? tabParam
      : "kline";
  const initialSource: SourceId =
    tableParam === "index_daily_bar" ? "index_daily_bar" : "daily_bar";
  const [source, setSource] = useState<SourceId>(initialSource);
  const [tab, setTab] = useState<TabId>(initialTab);
  const [meta, setMeta] = useState<TableMeta | null>(null);
  const [adjust, setAdjust] = useState("front");
  const [date, setDate] = useState("");
  const [code, setCode] = useState(
    codeParam || (initialSource === "index_daily_bar" ? "000300.SH" : "600519.SH")
  );
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [dateMin, setDateMin] = useState<string | null>(null);
  const [dateMax, setDateMax] = useState<string | null>(null);
  const [activePreset, setActivePreset] = useState<DatePresetId | null>("1y");
  const [datesLoading, setDatesLoading] = useState(true);
  const [filtersReady, setFiltersReady] = useState(false);
  const [codeFilter, setCodeFilter] = useState("");
  const [query, setQuery] = useState<QueryResult | null>(null);
  const [kline, setKline] = useState<KlinePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [klineLoading, setKlineLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [klineError, setKlineError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [sortCol, setSortCol] = useState("code");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [indexList, setIndexList] = useState<IndexInstrument[]>([]);
  const isIndex = source === "index_daily_bar";

  useEffect(() => {
    fetchTableMeta(source).then((m) => {
      setMeta(m);
      if (m.available_adjust_types?.length && !m.available_adjust_types.includes(adjust)) {
        setAdjust(m.available_adjust_types[0]);
      }
    });
  }, [source]);

  useEffect(() => {
    if (!isIndex) {
      setIndexList([]);
      return;
    }
    fetchIndexInstruments()
      .then((items) => {
        setIndexList(items);
        if (items.length && !items.some((it) => it.code === code)) {
          const hs = items.find((it) => it.code === "000300.SH");
          setCode((hs || items[0]).code);
        }
      })
      .catch(() => setIndexList([]));
  }, [isIndex]);

  useEffect(() => {
    setDatesLoading(true);
    setFiltersReady(false);
    fetchDateRange(isIndex ? "none" : adjust, source)
      .then((r) => {
        const max = r.max_date || todayISO();
        setDateMin(r.min_date);
        setDateMax(r.max_date);
        setDate((d) => d || max);
        const { from, to } = r.max_date
          ? defaultOneYearRange(max, r.min_date)
          : rangeForPreset("1y", max, r.min_date);
        setDateFrom(from);
        setDateTo(to);
        setActivePreset("1y");
        setFiltersReady(true);
      })
      .catch(() => {
        const max = todayISO();
        const { from, to } = rangeForPreset("1y", max);
        setDateFrom(from);
        setDateTo(to);
        setDate(max);
        setFiltersReady(true);
      })
      .finally(() => setDatesLoading(false));
  }, [adjust, source, isIndex]);

  const loadCrossSection = useCallback(async () => {
    if (!date) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDataQuery({
        table: source,
        view_mode: "cross_section",
        date,
        adjust: isIndex ? undefined : adjust,
        code: isIndex ? undefined : codeFilter || undefined,
        q: isIndex ? codeFilter || undefined : undefined,
        page,
        page_size: 100,
        sort_col: sortCol,
        sort_dir: sortDir,
      });
      setQuery({
        ...res,
        columns: res.columns?.length ? res.columns : meta?.columns || [],
      });
      if (isIndex && res.total === 0) {
        setError("指数日线为空。请先在②准备数据页使用「指数同步」。");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setQuery(null);
    } finally {
      setLoading(false);
    }
  }, [date, adjust, codeFilter, page, sortCol, sortDir, meta?.columns, source, isIndex]);

  const loadSeries = useCallback(
    async (overrides?: { code?: string; from?: string; to?: string }) => {
      const queryCode = (overrides?.code ?? code).trim();
      const from = overrides?.from ?? dateFrom;
      const to = overrides?.to ?? dateTo;
      if (!queryCode || !from || !to) return;
      setLoading(true);
      setError(null);
      try {
        const res = await fetchDataQuery({
          table: source,
          view_mode: "series",
          code: queryCode,
          date_from: from,
          date_to: to,
          adjust: isIndex ? undefined : adjust,
          page,
          page_size: 100,
          sort_col: sortCol || "date",
          sort_dir: sortDir,
        });
        setQuery({
          ...res,
          columns: res.columns?.length ? res.columns : meta?.columns || [],
        });
        if (res.rows[0]?.code && String(res.rows[0].code) !== code) {
          setCode(String(res.rows[0].code));
        }
        if (isIndex && res.total === 0) {
          setError("指数日线为空。请先在②准备数据页使用「指数同步」。");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setQuery(null);
      } finally {
        setLoading(false);
      }
    },
    [code, dateFrom, dateTo, adjust, page, sortCol, sortDir, meta?.columns, source, isIndex]
  );

  const queryKline = useCallback(
    async (overrides?: { code?: string; from?: string; to?: string }) => {
      const queryCode = (overrides?.code ?? code).trim();
      const from = overrides?.from ?? dateFrom;
      const to = overrides?.to ?? dateTo;
      if (!queryCode) {
        setKlineError(isIndex ? "请选择指数" : "请选择或输入股票代码/名称");
        return;
      }
      if (!from || !to) {
        setKlineError("请选择日期范围");
        return;
      }
      setKlineLoading(true);
      setKlineError(null);
      try {
        const res = await fetchKline({
          code: queryCode,
          date_from: from,
          date_to: to,
          adjust: isIndex ? "none" : adjust,
        });
        setKline(res);
        if (res.code && res.code !== code) setCode(res.code);
        if (res.empty) setKlineError(res.hint || "暂无 K 线数据");
      } catch (err) {
        setKlineError(err instanceof Error ? err.message : String(err));
        setKline(null);
      } finally {
        setKlineLoading(false);
      }
    },
    [code, dateFrom, dateTo, adjust, isIndex]
  );

  useEffect(() => {
    if (tab === "cross_section") loadCrossSection();
  }, [tab, loadCrossSection]);

  useEffect(() => {
    if (!filtersReady || tab === "cross_section") return;
    if (tab === "series") {
      void loadSeries();
      void queryKline();
    } else if (tab === "kline") {
      void queryKline();
    }
  }, [tab, filtersReady, source]);

  function handleDateRangeChange(from: string, to: string, preset?: DatePresetId | null) {
    setDateFrom(from);
    setDateTo(to);
    setActivePreset(preset ?? null);
    if (tab === "series") {
      void loadSeries({ from, to });
      void queryKline({ from, to });
    } else if (tab === "kline") {
      void queryKline({ from, to });
    }
  }

  function runCurrentQuery() {
    if (tab === "cross_section") {
      void loadCrossSection();
      return;
    }
    if (tab === "series") {
      void loadSeries();
      void queryKline();
      return;
    }
    void queryKline();
  }

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
    void queryKline({ code: c });
  }

  function switchSource(next: SourceId) {
    if (next === source) return;
    setSource(next);
    setPage(1);
    setQuery(null);
    setKline(null);
    setError(null);
    setKlineError(null);
    setCodeFilter("");
    setCode(next === "index_daily_bar" ? "000300.SH" : "600519.SH");
    setTab("cross_section");
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
  const sources: { id: SourceId; label: string }[] = [
    { id: "daily_bar", label: "股票日线" },
    { id: "index_daily_bar", label: "指数日线" },
  ];

  const canQuerySeries = Boolean(code.trim() && dateFrom && dateTo && !datesLoading);
  const indexOptions = indexList.map((it) => ({
    id: it.code,
    label: `${it.name || it.code} ${it.code}${it.kind === "industry" ? " · 行业" : " · 基准"}`,
  }));

  return (
    <div>
      <PageCallout>
        {isIndex ? (
          <>
            浏览基准与申万一级行业指数（独立表，不复权）。空表请先在{" "}
            <Link to="/data#index-sync" className="text-emerald-400 hover:underline">
              ② 准备数据 · 指数同步
            </Link>{" "}
            单独拉取，不必再跑一遍全市场个股日线。
          </>
        ) : (
          <>
            浏览已同步的日线与证券列表。若无数据或名称显示「—」，请先在{" "}
            <Link to="/data" className="text-emerald-400 hover:underline">
              ② 准备数据
            </Link>{" "}
            同步日线，并在「其他操作」中点「补全股票名称」。全量同步会自动补全名称；增量同步默认跳过（避免 5000+ 逐只调 QMT 拖慢更新）。
          </>
        )}
      </PageCallout>

      <div className="mb-3 flex flex-wrap gap-2">
        {sources.map((s) => (
          <button
            key={s.id}
            type="button"
            className={source === s.id ? "btn-primary" : "btn-secondary"}
            onClick={() => switchSource(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>

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

      <div className="card mb-4 space-y-4">
        {tab === "cross_section" && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {!isIndex && (
              <PresetSelect label="复权" value={adjust} options={adjustOptions} onChange={setAdjust} />
            )}
            <label className="block text-sm">
              <span className="label">交易日</span>
              <input
                type="date"
                className="input"
                value={date}
                min={dateMin || undefined}
                max={dateMax || todayISO()}
                onChange={(e) => {
                  setDate(e.target.value);
                  setPage(1);
                }}
              />
            </label>
            <label className="block text-sm">
              <span className="label">{isIndex ? "代码/名称/类型（可选）" : "代码或名称（可选）"}</span>
              <input
                className="input"
                placeholder={isIndex ? "000300 或 沪深300 或 基准" : "600519 或 贵州茅台"}
                value={codeFilter}
                onChange={(e) => {
                  setCodeFilter(e.target.value);
                  setPage(1);
                }}
              />
            </label>
            <div className="flex items-end">
              <button type="button" className="btn-primary w-full sm:w-auto" onClick={loadCrossSection}>
                查询
              </button>
            </div>
          </div>
        )}

        {(tab === "series" || tab === "kline") && (
          <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {!isIndex && (
                <PresetSelect label="复权" value={adjust} options={adjustOptions} onChange={setAdjust} />
              )}
              <div className={isIndex ? "lg:col-span-3" : "lg:col-span-2"}>
                {isIndex ? (
                  indexOptions.length ? (
                    <PresetSelect
                      label="指数"
                      value={code}
                      options={indexOptions}
                      onChange={(next) => {
                        setCode(next);
                        if (tab === "kline") void queryKline({ code: next });
                        if (tab === "series") {
                          void loadSeries({ code: next });
                          void queryKline({ code: next });
                        }
                      }}
                    />
                  ) : (
                    <p className="text-sm text-amber-200">
                      尚未发现已同步指数。请先在{" "}
                      <Link to="/data#index-sync" className="underline">
                        ② 准备数据 · 指数同步
                      </Link>
                      。
                    </p>
                  )
                ) : (
                  <StockSearchInput
                    value={code}
                    onChange={setCode}
                    onResolved={(resolved) => {
                      if (tab === "kline") void queryKline({ code: resolved });
                      if (tab === "series") {
                        void loadSeries({ code: resolved });
                        void queryKline({ code: resolved });
                      }
                    }}
                  />
                )}
              </div>
            </div>
            <DateRangePicker
              from={dateFrom}
              to={dateTo}
              min={dateMin}
              max={dateMax}
              activePreset={activePreset}
              loading={datesLoading}
              onChange={handleDateRangeChange}
            />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-4">
              <p className="text-xs text-slate-500">
                {canQuerySeries
                  ? isIndex
                    ? "指数不复权；点快捷日期后会自动查询"
                    : "支持代码/名称搜索；点快捷日期后会自动查询"
                  : "正在准备默认日期…"}
              </p>
              <button
                type="button"
                className="btn-primary min-w-24"
                onClick={runCurrentQuery}
                disabled={!canQuerySeries}
              >
                {klineLoading || loading ? "查询中…" : "查询"}
              </button>
            </div>
          </>
        )}
      </div>

      {(tab === "cross_section" || tab === "series") && (
        <div className="card">
          {error && (
            <p className="mb-3 text-sm text-red-300">
              {error}{" "}
              <Link to="/data" className="text-emerald-300 underline">
                ② 准备数据
              </Link>
            </p>
          )}
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
            <p className="text-sm text-slate-500">{loading ? "加载中…" : "请选择条件后查询"}</p>
          )}
        </div>
      )}

      {(tab === "series" || tab === "kline") && (
        <div className="card mt-4">
          {klineError && !klineLoading && (
            <div className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              {klineError}
              {(klineError.includes("同步") || klineError.includes("指数日线")) && (
                <>
                  {" "}
                  <Link to={klineError.includes("指数") ? "/data#index-sync" : "/data"} className="text-emerald-300 underline">
                    {klineError.includes("指数") ? "去同步指数" : "去同步数据"}
                  </Link>
                </>
              )}
            </div>
          )}
          <CandlestickChart data={kline} loading={klineLoading} />
        </div>
      )}
    </div>
  );
}
