import { apiGet } from "./api";

/** Load persisted job result after navigation/remount. */
export async function fetchJobRecord(jobId: string): Promise<Record<string, unknown>> {
  return apiGet<Record<string, unknown>>(`/api/jobs/${jobId}`);
}

export function resultFromJobRecord(job: Record<string, unknown>): Record<string, unknown> | null {
  const raw = job.result_json;
  if (!raw) return null;
  if (typeof raw === "object") return raw as Record<string, unknown>;
  try {
    return JSON.parse(String(raw));
  } catch {
    return null;
  }
}
