export type StatusResp = {
  ok: boolean;
  uid: string;
  has_tokens: boolean;
  expires_at: number;
  expires_in_sec: number | null;
  token_path?: string | null;
  redirect_uri_effective?: string | null;
};

const BASE = (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "";

function normalizeBase(url?: string): string {
  const s = (url ?? "").trim();
  return s.replace(/\/+$/, "");
}

export function buildUrl(path: string): string {
  const base = normalizeBase(BASE);
  if (!base) return path; // fallback i dev
  // tåler base med /api eller uten
  const b = base.endsWith("/api") ? base.slice(0, -4) : base;
  return `${b}${path.startsWith("/") ? "" : "/"}${path}`;
}

export async function fetchStatus(): Promise<StatusResp> {
  const url = buildUrl("/status");
  const res = await fetch(url, {
    method: "GET",
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(`status failed: HTTP ${res.status}`);
  }
  return (await res.json()) as StatusResp;
}

export function tokenState(st: StatusResp | null): "unknown" | "missing" | "expired" | "valid" {
  if (!st) return "unknown";
  if (st.has_tokens !== true) return "missing";
  const exp = typeof st.expires_in_sec === "number" ? st.expires_in_sec : null;
  if (exp !== null && exp <= 0) return "expired";
  return "valid";
}
