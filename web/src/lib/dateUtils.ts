export function todayISO(): string {
  const d = new Date();
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function subtractMonths(isoDate: string, months: number): string {
  const d = new Date(`${isoDate}T12:00:00`);
  d.setMonth(d.getMonth() - months);
  return d.toISOString().slice(0, 10);
}

export function subtractYears(isoDate: string, years: number): string {
  const d = new Date(`${isoDate}T12:00:00`);
  d.setFullYear(d.getFullYear() - years);
  return d.toISOString().slice(0, 10);
}

export function clampDate(date: string, min?: string | null, max?: string | null): string {
  if (min && date < min) return min;
  if (max && date > max) return max;
  return date;
}

export function defaultOneYearRange(maxDate: string, minDate?: string | null): { from: string; to: string } {
  const to = maxDate;
  const from = clampDate(subtractYears(maxDate, 1), minDate, maxDate);
  return { from, to };
}

export type DatePresetId = "1m" | "3m" | "6m" | "1y" | "all";

export function rangeForPreset(
  preset: DatePresetId,
  maxDate: string,
  minDate?: string | null
): { from: string; to: string } {
  const to = maxDate;
  if (preset === "all") {
    return { from: minDate || to, to };
  }
  const months = preset === "1m" ? 1 : preset === "3m" ? 3 : preset === "6m" ? 6 : 12;
  return { from: clampDate(subtractMonths(to, months), minDate, to), to };
}
