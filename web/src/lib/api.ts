import React from "react";

const API = "";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : "{}",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function useJobProgress(onUpdate: (data: Record<string, unknown>) => void) {
  React.useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/jobs`);
    ws.onmessage = (ev) => {
      try {
        onUpdate(JSON.parse(ev.data));
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, [onUpdate]);
}
