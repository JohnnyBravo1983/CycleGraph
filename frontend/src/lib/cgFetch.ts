// SSOT: all frontend HTTP calls should go through this helper.
// - Always uses VITE_BACKEND_BASE (or localhost fallback)
// - Always includes cookies (credentials: "include")
// - Provides consistent JSON parsing + error handling

export function cgBaseUrl(): string {
  const raw = (import.meta as any)?.env?.VITE_BACKEND_BASE ?? "http://localhost:5175";
  const s = String(raw || "").trim();
  return s.endsWith("/") ? s.slice(0, -1) : s;
}

export type CgError = {
  status: number;
  detail?: string;
  bodyText?: string;
};

async function _readTextSafe(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return "";
  }
}

export async function cgFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const base = cgBaseUrl();
  const url = path.startsWith("http")
    ? path
    : `${base}${path.startsWith("/") ? "" : "/"}${path}`;

  const res = await fetch(url, {
    ...init,
    // IMPORTANT: include cookies for cross-site (Vercel -> Fly) auth
    credentials: "include",
    headers: {
      ...(init.headers || {}),
    },
  });

  return res;
}

export async function cgFetchJSON<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await cgFetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });

  if (!res.ok) {
    const txt = await _readTextSafe(res);
    let detail: string | undefined;
    try {
      const j = JSON.parse(txt);
      detail = j?.detail ?? j?.error;
    } catch {}
    const err: CgError = { status: res.status, detail, bodyText: txt };
    throw err;
  }

  const txt = await _readTextSafe(res);
  if (!txt) return {} as T;
  return JSON.parse(txt) as T;
}
