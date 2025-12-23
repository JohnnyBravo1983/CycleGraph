// src/lib/cgApi.ts
export type StatusResp = {
  ok: boolean;
  uid?: string;
  has_tokens?: boolean;
  expires_at?: number;
  expires_in_sec?: number;
  token_path?: string;
  [k: string]: unknown;
};

export type ImportResp = {
  ok?: boolean;
  reason?: string;
  samples_len?: number;
  analyze?: { status_code?: number; [k: string]: unknown };
  [k: string]: unknown;
};

export type SessionListItem = {
  session_id?: string;
  ride_id?: string | number;
  debug_source_path?: string;
  [k: string]: unknown;
};

function baseUrl(): string {
  const raw = (import.meta as any).env?.VITE_BACKEND_BASE || "http://localhost:5175";
  return String(raw).replace(/\/$/, "");
}

async function cgFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${baseUrl()}${path.startsWith("/") ? "" : "/"}${path}`;

  const res = await fetch(url, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });

  const text = await res.text();
  let json: any = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {}

  if (!res.ok) {
    const msg = (json && (json.detail || json.reason || json.error)) || `HTTP ${res.status} ${res.statusText}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }

  return json as T;
}

export const cgApi = {
  baseUrl,
  status: () => cgFetch<StatusResp>("/status", { method: "GET" }),
  importRide: (rid: string) =>
    cgFetch<ImportResp>(`/api/strava/import/${encodeURIComponent(rid)}`, { method: "POST", body: "{}" }),
  listAll: () => cgFetch<SessionListItem[]>("/api/sessions/list/all", { method: "GET" }),
};
