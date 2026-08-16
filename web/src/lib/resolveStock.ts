import { searchInstruments, type InstrumentRow } from "./dataApi";

function formatLabel(row: InstrumentRow): string {
  const name = row.name?.trim();
  return name ? `${name}（${row.code}）` : row.code;
}

function normalizeDigitsCode(raw: string): string | null {
  const q = raw.trim().toUpperCase();
  const m = q.match(/^(\d{6})(?:\.(SH|SZ))?$/);
  if (!m) return null;
  const digits = m[1];
  const suffix = m[2];
  if (suffix) return `${digits}.${suffix}`;
  if (digits.startsWith("6") || digits.startsWith("5") || digits.startsWith("9")) {
    return `${digits}.SH`;
  }
  return `${digits}.SZ`;
}

/** Resolve typed code or name to a single instrument row. */
export async function resolveStockQuery(raw: string): Promise<InstrumentRow | null> {
  const q = raw.trim();
  if (!q) return null;

  const fromDigits = normalizeDigitsCode(q);
  if (fromDigits) {
    const rows = await searchInstruments(fromDigits, 5);
    const exact = rows.find((row) => row.code === fromDigits);
    return exact || { code: fromDigits, name: null };
  }

  const rows = await searchInstruments(q, 20);
  if (!rows.length) return null;

  const exact =
    rows.find((row) => row.code === q) ||
    rows.find((row) => row.name === q) ||
    rows.find((row) => formatLabel(row) === q);
  if (exact) return exact;

  if (rows.length === 1) return rows[0];
  return null;
}

export function isValidStockCode(code: string): boolean {
  return /^\d{6}\.(SH|SZ)$/.test(code.trim().toUpperCase());
}
