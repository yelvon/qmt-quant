import { useEffect, useRef } from "react";
import { fetchJobRecord, resultFromJobRecord } from "./jobResult";

const MAX_ATTEMPTS = 12;
const RETRY_MS = 500;

/** Load persisted job result once when a tracked job reaches ``completed``. */
export function useJobResultLoader(
  active: boolean,
  jobId: string,
  status: string,
  onResult: (payload: Record<string, unknown>) => void | Promise<void>
) {
  const handledRef = useRef("");
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  useEffect(() => {
    if (!active || !jobId || status !== "completed") return;
    if (handledRef.current === jobId) return;

    let cancelled = false;

    (async () => {
      for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
        if (cancelled) return;
        try {
          const record = await fetchJobRecord(jobId);
          const payload = resultFromJobRecord(record);
          if (payload && !cancelled) {
            handledRef.current = jobId;
            await onResultRef.current(payload);
            return;
          }
        } catch {
          /* retry */
        }
        if (attempt < MAX_ATTEMPTS - 1) {
          await new Promise((r) => window.setTimeout(r, RETRY_MS));
        }
      }
      if (!cancelled) {
        handledRef.current = "";
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [active, jobId, status]);
}
