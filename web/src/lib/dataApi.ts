import { apiGet } from "./api";

export type ColumnMeta = { id: string; label: string };

export type TableMeta = {
  table: string;
  label: string;
  columns: ColumnMeta[];
  view_modes: string[];
  default_view_mode: string;
  adjust_options: { id: string; label: string }[];
  available_adjust_types?: string[];
};

export type QueryResult = {
  ok: boolean;
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  page_size: number;
  columns: ColumnMeta[];
  table: string;
  view_mode: string;
};

export type KlinePayload = {
  ok: boolean;
  code: string;
  adjust: string;
  dates: string[];
  ohlc: number[][];
  volume: number[];
  empty: boolean;
  hint?: string;
};

export type DateRange = {
  ok: boolean;
  min_date: string | null;
  max_date: string | null;
  adjust: string;
};

export function fetchTableMeta(table: string): Promise<TableMeta> {
  return apiGet(`/api/data/meta?table=${encodeURIComponent(table)}`);
}

export function fetchDataQuery(
  params: Record<string, string | number | boolean | undefined>
): Promise<QueryResult> {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v !== undefined && v !== null) qs.set(k, String(v));
  });
  return apiGet(`/api/data/query?${qs.toString()}`);
}

export function fetchKline(params: {
  code: string;
  date_from?: string;
  date_to?: string;
  adjust?: string;
}): Promise<KlinePayload> {
  const qs = new URLSearchParams({ code: params.code });
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  if (params.adjust) qs.set("adjust", params.adjust);
  return apiGet(`/api/data/kline?${qs.toString()}`);
}

export function fetchDateRange(adjust = "front"): Promise<DateRange> {
  return apiGet(`/api/data/dates?adjust=${encodeURIComponent(adjust)}`);
}

export type InstrumentRow = {
  code: string;
  name?: string | null;
  list_date?: string | null;
  delist_date?: string | null;
  is_st?: boolean | number | null;
};

export async function searchInstruments(q: string, pageSize = 20): Promise<InstrumentRow[]> {
  const res = await fetchDataQuery({
    table: "instrument",
    view_mode: "instrument_list",
    q,
    page_size: pageSize,
    sort_col: "code",
    sort_dir: "asc",
  });
  return res.rows as InstrumentRow[];
}
