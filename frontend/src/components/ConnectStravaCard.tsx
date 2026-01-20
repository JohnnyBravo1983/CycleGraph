// src/components/ConnectStravaCard.tsx

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
  return (json as any).detail ?? (json as any).reason ?? (json as any).error ?? (json as any).message ?? null;
}

async function cgFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${baseUrl()}${path.startsWith("/") ? "" : "/"}${path}`;

  const res = await fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });

  const text = await res.text().catch(() => "");

  let json: unknown = null;
  try {
    json = text ? (JSON.parse(text) as unknown) : null;
  } catch {
    json = null;
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

  return (json ?? null) as T;
}

export const cgApi = {
  baseUrl,

  status: () => cgFetch<StatusResp>("/status", { method: "GET" }),

  // ✅ Strava status (SSOT for "Connected")
  stravaStatus: () => cgFetch<StatusResp>("/api/auth/strava/status", { method: "GET" }),

  importRide: (rid: string) =>
    cgFetch<ImportResp>(`/api/strava/import/${encodeURIComponent(rid)}`, {
      method: "POST",
      body: "{}",
    }),

  listAll: () => cgFetch<SessionListItem[]>("/api/sessions/list/all", { method: "GET" }),
};

// -----------------------------
// PATCH B: auto-refresh status after OAuth return
// -----------------------------
import React, { useEffect, useMemo, useState } from "react";

function fmtDur(sec: number): string {
  const s = Math.abs(Math.trunc(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

type TokenState = "unknown" | "missing" | "expired" | "valid";

function getTokenState(st: StatusResp | null): TokenState {
  if (!st) return "unknown";
  if (st.has_tokens !== true) return "missing";
  const exp = typeof st.expires_in_sec === "number" ? st.expires_in_sec : null;
  if (exp !== null && exp <= 0) return "expired";
  return "valid";
}

export default function ConnectStravaCard() {
  const [s, setS] = useState<StatusResp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // ✅ PATCH B: refresh on mount + a couple retries (covers callback redirect timing)
  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      setBusy(true);
      try {
        const r = await cgApi.stravaStatus();
        if (!cancelled) {
          setS(r);
          setErr(null);
        }
      } catch (e: any) {
        if (!cancelled) setErr(String(e?.message ?? e));
      } finally {
        if (!cancelled) setBusy(false);
      }
    }

    refresh();
    const t1 = window.setTimeout(refresh, 800);
    const t2 = window.setTimeout(refresh, 1600);

    return () => {
      cancelled = true;
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, []);

  const tokenState = useMemo(() => getTokenState(s), [s]);
  const tokenValid = tokenState === "valid";
  const tokenExpired = tokenState === "expired";
  const hasTokens = s?.has_tokens === true;

  let expiresText: string | null = null;
  if (s && typeof s.expires_in_sec === "number") {
    if (s.expires_in_sec >= 0) expiresText = `expires in ${fmtDur(s.expires_in_sec)}`;
    else expiresText = `expired for ${fmtDur(s.expires_in_sec)}`;
  }

  function connectStrava() {
    const nextRaw = `${window.location.origin}/onboarding`;
    const url = `${cgApi.baseUrl()}/api/auth/strava/login?next=${encodeURIComponent(nextRaw)}`;
    window.open(url, "_self");
  }

  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Koble til Strava</h2>
          <p className="text-sm text-slate-600 mt-1">
            For å hente turer og bygge din første analyse trenger vi tilgang til Strava.
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Backend: <span className="font-mono">{cgApi.baseUrl()}</span>
          </p>
        </div>

        <div className="shrink-0">
          {tokenValid ? (
            <div className="px-3 py-2 rounded border text-sm text-slate-700 bg-slate-50">
              Strava er tilkoblet ✅
            </div>
          ) : (
            <button
              type="button"
              onClick={connectStrava}
              disabled={busy}
              className="px-3 py-2 rounded bg-slate-900 text-white text-sm hover:bg-slate-800 disabled:bg-slate-400"
              title={tokenExpired ? "Token er utløpt – koble til på nytt" : "Koble til Strava"}
            >
              {busy ? "Sjekker…" : tokenExpired ? "Reconnect Strava" : "Connect Strava"}
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 text-sm">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-700">
          <div>
            has_tokens:{" "}
            <span className="font-semibold">{String(s?.has_tokens ?? "unknown")}</span>
          </div>
          <div>
            expires_in_sec:{" "}
            <span className="font-semibold">{String(s?.expires_in_sec ?? "n/a")}</span>
            {expiresText ? <span className="opacity-70"> ({expiresText})</span> : null}
          </div>
          <div>
            uid: <span className="font-mono text-xs">{String(s?.uid ?? "n/a")}</span>
          </div>
        </div>

        {tokenExpired ? (
          <div className="mt-2 text-xs text-amber-700">
            Strava-token er utløpt. Trykk <b>Reconnect Strava</b> for å koble til på nytt.
          </div>
        ) : null}

        {!hasTokens && s ? (
          <div className="mt-2 text-xs text-slate-600">
            Du har ikke koblet til Strava ennå. Trykk{" "}
            <span className="font-semibold">Connect Strava</span> og fullfør innlogging – så
            oppdateres status automatisk når du kommer tilbake.
          </div>
        ) : null}

        {err ? <div className="mt-2 text-xs text-red-600 whitespace-pre-wrap">{err}</div> : null}
      </div>
    </div>
  );
}
