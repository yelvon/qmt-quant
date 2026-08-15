import React, { useEffect, useId, useRef, useState } from "react";
import { searchInstruments } from "../lib/dataApi";

type InstrumentRow = { code: string; name?: string | null };

type Props = {
  value: string;
  onChange: (code: string) => void;
  onResolved?: (code: string) => void;
  label?: string;
  placeholder?: string;
};

function formatLabel(row: InstrumentRow): string {
  const name = row.name?.trim();
  return name ? `${name}（${row.code}）` : row.code;
}

function looksLikeSelectedLabel(text: string): boolean {
  return /（.+\..+）$/.test(text.trim());
}

export default function StockSearchInput({
  value,
  onChange,
  onResolved,
  label = "股票",
  placeholder = "输入代码或名称，如 600519 或 贵州茅台",
}: Props) {
  const listId = useId();
  const blurTimer = useRef<number | null>(null);
  const [text, setText] = useState("");
  const [options, setOptions] = useState<InstrumentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!value) {
      setText("");
      return;
    }
    let cancelled = false;
    searchInstruments(value, 8)
      .then((rows) => {
        if (cancelled) return;
        const exact = rows.find((row) => row.code === value);
        setText(exact ? formatLabel(exact) : value);
      })
      .catch(() => {
        if (!cancelled) setText(value);
      });
    return () => {
      cancelled = true;
    };
  }, [value]);

  useEffect(() => {
    const q = text.trim();
    if (!q || looksLikeSelectedLabel(q)) {
      setOptions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      setLoading(true);
      searchInstruments(q, 20)
        .then((rows) => {
          setOptions(rows);
          setOpen(rows.length > 0);
        })
        .finally(() => setLoading(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [text]);

  function pick(row: InstrumentRow) {
    setText(formatLabel(row));
    setOpen(false);
    setOptions([]);
    onChange(row.code);
    onResolved?.(row.code);
  }

  async function commitTypedCode() {
    const q = text.trim();
    if (!q) {
      onChange("");
      return;
    }
    if (looksLikeSelectedLabel(q)) {
      return;
    }
    const matched =
      options.find((row) => row.code === q || formatLabel(row) === q) ||
      (await searchInstruments(q, 5).then((rows) =>
        rows.find((row) => row.code === q || row.name === q)
      ));
    if (matched) {
      pick(matched);
      return;
    }
    if (/^\d{6}(\.(SH|SZ))?$/i.test(q)) {
      const normalized = q.toUpperCase().includes(".") ? q.toUpperCase() : q;
      onChange(normalized);
      onResolved?.(normalized);
      return;
    }
    const candidates = options.length ? options : await searchInstruments(q, 5);
    if (candidates.length === 1) {
      pick(candidates[0]);
      return;
    }
    if (candidates.length > 1) {
      setOptions(candidates);
      setOpen(true);
      return;
    }
    onChange(q);
  }

  return (
    <div className="relative">
      <label className="block text-sm">
        <span className="label">{label}</span>
        <input
          className="input"
          value={text}
          placeholder={placeholder}
          list={options.length ? listId : undefined}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            if (options.length) setOpen(true);
          }}
          onBlur={() => {
            blurTimer.current = window.setTimeout(() => {
              setOpen(false);
              void commitTypedCode();
            }, 150);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (blurTimer.current) window.clearTimeout(blurTimer.current);
              setOpen(false);
              void commitTypedCode();
            }
            if (e.key === "Escape") setOpen(false);
          }}
        />
      </label>
      {loading && <p className="mt-1 text-xs text-slate-500">搜索中…</p>}
      {open && options.length > 0 && (
        <ul
          id={listId}
          className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-slate-700 bg-slate-950 py-1 shadow-lg"
        >
          {options.map((row) => (
            <li key={row.code}>
              <button
                type="button"
                className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-800"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(row)}
              >
                <span className="text-slate-100">{row.name || row.code}</span>
                <span className="ml-2 text-xs text-slate-500">{row.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
