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
  const raw = import.meta.env.VITE_BACKEND_BASE ?? "http://localhost:5175";
  return String(raw).replace(/\/$/, "");
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function extractErrorMessage(json: unknown): unknown {
  if (!isRecord(json)) return null;
  return json.detail ?? json.reason ?? json.error ?? json.message ?? null;
}

async function cgFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${baseUrl()}${path.startsWith("/") ? "" : "/"}${path}`;

  const res = await fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  const text = await res.text();

  let json: unknown = null;
  try {
    json = text ? (JSON.parse(text) as unknown) : null;
  } catch {
    json = null; // Non-JSON response
  }

  if (!res.ok) {
    const msgFromJson = extractErrorMessage(json);

    const msg =
      (typeof msgFromJson === "string" && msgFromJson) ||
      (msgFromJson ? JSON.stringify(msgFromJson) : null) ||
      (text ? text : null) ||
      `HTTP ${res.status} ${res.statusText}`;

    throw new Error(msg);
  }

  return json as T;
}

export const cgApi = {
  baseUrl,
  status: () => cgFetch<StatusResp>("/status", { method: "GET" }),

  importRide: (rid: string) =>
    cgFetch<ImportResp>(`/api/strava/import/${encodeURIComponent(rid)}`, {
      method: "POST",
      body: "{}",
    }),

  listAll: () =>
    cgFetch<SessionListItem[]>("/api/sessions/list/all", { method: "GET" }),
};
