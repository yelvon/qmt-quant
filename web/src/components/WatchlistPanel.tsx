import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPut } from "../lib/api";
import { parseApiError } from "../lib/errorMessages";
import { resolveStockQuery } from "../lib/resolveStock";
import StockSearchInput, { type StockSearchInputHandle } from "./StockSearchInput";

type WatchlistItem = { code: string; name?: string };

type Props = {
  onSyncWatchlist?: () => void;
  compact?: boolean;
};

export default function WatchlistPanel({ onSyncWatchlist, compact = false }: Props) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const [addCode, setAddCode] = useState("");
  const [addText, setAddText] = useState("");
  const searchRef = useRef<StockSearchInputHandle>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiGet<{ items: WatchlistItem[] }>("/api/watchlist");
      setItems(res.items || []);
    } catch (err) {
      setError(parseApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function persist(nextItems: WatchlistItem[]) {
    setSaving(true);
    setError(null);
    try {
      const res = await apiPut<{ items: WatchlistItem[] }>("/api/watchlist", {
        codes: nextItems.map((i) => i.code),
      });
      setItems(res.items || []);
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 2000);
    } catch (err) {
      setError(parseApiError(err instanceof Error ? err.message : String(err)));
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function addResolved(resolved: { code: string; name?: string | null }) {
    if (items.some((i) => i.code === resolved.code)) {
      setError("该股票已在自选池中");
      return;
    }
    setAddCode("");
    setAddText("");
    setError(null);
    await persist([
      ...items,
      { code: resolved.code, name: resolved.name?.trim() || "" },
    ]);
  }

  async function addStockFromInput(raw: string) {
    const query = raw.trim();
    if (!query) return;

    const resolved =
      (await searchRef.current?.resolve()) || (await resolveStockQuery(query));
    if (!resolved) {
      setError("请从下拉列表选择股票，或输入完整的六位代码（如 600036）");
      return;
    }
    await addResolved(resolved);
  }

  async function removeStock(code: string) {
    await persist(items.filter((i) => i.code !== code));
  }

  return (
    <div id="watchlist" className={compact ? "space-y-3" : "card mb-4 scroll-mt-24 space-y-4"}>
      {!compact && (
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-medium text-slate-100">我的自选池</h2>
          <span className="text-xs text-slate-500">
            {loading ? "加载中…" : saving ? "保存中…" : savedFlash ? "已保存" : `共 ${items.length} 只`}
          </span>
        </div>
      )}

      {!compact && (
        <p className="text-sm text-slate-400">
          在回测/扫描里选「我的自选池」时使用此列表。输入名称后请<strong className="font-normal text-slate-300">点击下拉选项</strong>
          或按 Enter 确认，再添加。
        </p>
      )}

      {error && <p className="text-sm text-red-300">{error}</p>}

      <div className="flex flex-wrap gap-2">
        {loading && items.length === 0 ? (
          <span className="text-sm text-slate-500">加载自选池…</span>
        ) : items.length === 0 ? (
          <span className="text-sm text-slate-500">还没有股票，在下方搜索添加。</span>
        ) : (
          items.map((item) => (
            <span
              key={item.code}
              className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1 text-sm text-slate-200"
            >
              <span className="font-mono text-xs text-emerald-300/90">{item.code}</span>
              {item.name ? <span className="max-w-[8rem] truncate text-slate-400">{item.name}</span> : null}
              <button
                type="button"
                className="ml-0.5 rounded px-1 text-slate-500 hover:bg-slate-800 hover:text-red-300 disabled:opacity-40"
                disabled={saving}
                aria-label={`移除 ${item.code}`}
                onClick={() => void removeStock(item.code)}
              >
                ×
              </button>
            </span>
          ))
        )}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[16rem] flex-1 max-w-md">
          <StockSearchInput
            ref={searchRef}
            label="添加股票"
            value={addCode}
            onChange={setAddCode}
            onTextChange={setAddText}
            onPick={(row) => void addResolved(row)}
          />
        </div>
        <button
          type="button"
          className="btn-secondary shrink-0"
          disabled={saving || !(addText.trim() || addCode.trim())}
          onClick={() => void addStockFromInput(addText || addCode)}
        >
          添加
        </button>
      </div>

      {!compact && (
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-3 text-xs text-slate-500">
          {onSyncWatchlist && items.length > 0 && (
            <button type="button" className="btn-secondary text-xs" onClick={onSyncWatchlist}>
              同步自选池日线
            </button>
          )}
          <span>回测/扫描最多取前 50 只</span>
          <Link to="/research" className="underline hover:text-slate-300">
            去策略回测
          </Link>
        </div>
      )}
    </div>
  );
}
