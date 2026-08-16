import React, { useEffect, useId, useImperativeHandle, useRef, useState } from "react";
import { resolveStockQuery } from "../lib/resolveStock";
import { searchInstruments, type InstrumentRow } from "../lib/dataApi";

export type StockSearchInputHandle = {
  resolve: () => Promise<InstrumentRow | null>;
  getText: () => string;
};

type Props = {
  value: string;
  onChange: (code: string) => void;
  onTextChange?: (text: string) => void;
  onPick?: (row: InstrumentRow) => void;
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

const StockSearchInput = React.forwardRef<StockSearchInputHandle, Props>(function StockSearchInput(
  {
    value,
    onChange,
    onTextChange,
    onPick,
    onResolved,
    label = "股票",
    placeholder = "输入代码或名称，如 600519 或 贵州茅台",
  },
  ref
) {
  const listId = useId();
  const blurTimer = useRef<number | null>(null);
  const textRef = useRef("");
  const [text, setText] = useState("");
  const [options, setOptions] = useState<InstrumentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  textRef.current = text;

  useEffect(() => {
    onTextChange?.(text);
  }, [text, onTextChange]);

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
    onPick?.(row);
    onResolved?.(row.code);
  }

  async function resolveCurrentInput(): Promise<InstrumentRow | null> {
    const q = textRef.current.trim();
    if (!q) return null;
    if (looksLikeSelectedLabel(q)) {
      const codeMatch = q.match(/（(.+\..+)）$/);
      if (codeMatch) {
        return { code: codeMatch[1], name: q.replace(/（.+）$/, "") };
      }
    }
    const matched =
      options.find((row) => row.code === q || formatLabel(row) === q) ||
      (await resolveStockQuery(q));
    if (matched) {
      onChange(matched.code);
      setText(formatLabel(matched));
      return matched;
    }
    return null;
  }

  useImperativeHandle(ref, () => ({
    resolve: resolveCurrentInput,
    getText: () => textRef.current,
  }));

  async function commitTypedCode() {
    const q = text.trim();
    if (!q) {
      onChange("");
      return;
    }
    if (looksLikeSelectedLabel(q)) {
      return;
    }
    const resolved = await resolveCurrentInput();
    if (resolved) {
      return;
    }
    const candidates = options.length ? options : await searchInstruments(q, 5);
    if (candidates.length > 1) {
      setOptions(candidates);
      setOpen(true);
    }
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
});

export default StockSearchInput;
