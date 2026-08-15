export type RangePresetId = "1y" | "3y" | "5y" | "10y" | "20y" | "all";

export const FULL_SYNC_RANGE_OPTIONS: { id: RangePresetId; label: string }[] = [
  { id: "1y", label: "1 年" },
  { id: "3y", label: "3 年" },
  { id: "5y", label: "5 年" },
  { id: "10y", label: "10 年" },
  { id: "20y", label: "20 年" },
  { id: "all", label: "尽可能早（约 2005 年起，以 QMT 为准）" },
];

export function todayISO(): string {
  const d = new Date();
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function resolveRangePreset(
  preset: RangePresetId,
  maxDate?: string | null
): { start: string; end: string; label: string } {
  const endDate = maxDate ? new Date(`${maxDate}T12:00:00`) : new Date();
  const end = maxDate || todayISO();
  const mapping: Record<string, number> = {
    "1y": 365,
    "3y": 365 * 3,
    "5y": 365 * 5,
    "10y": 365 * 10,
    "20y": 365 * 20,
  };
  let start: string;
  if (preset === "all") {
    start = "2005-01-01";
  } else {
    const days = mapping[preset] ?? mapping["3y"];
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - days);
    start = startDate.toISOString().slice(0, 10);
  }
  const opt = FULL_SYNC_RANGE_OPTIONS.find((o) => o.id === preset);
  return { start, end, label: opt?.label || preset };
}

export function formatRangeSummary(start: string, end: string): string {
  return `${start} ~ ${end}`;
}

export function countCalendarDays(start: string, end: string): number {
  const a = new Date(`${start}T12:00:00`).getTime();
  const b = new Date(`${end}T12:00:00`).getTime();
  return Math.max(1, Math.round((b - a) / 86400000) + 1);
}
