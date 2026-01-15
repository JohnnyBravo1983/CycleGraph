import React from "react";
import { useLocation } from "react-router-dom";
import {
  cgApi,
  type ImportResp,
  type SessionListItem,
  type StatusResp,
} from "../lib/cgApi";

type TokenState = "unknown" | "missing" | "expired" | "valid";

function getTokenState(st: StatusResp | null): TokenState {
  if (!st) return "unknown";
  if (st.has_tokens !== true) return "missing";
  const exp = typeof st.expires_in_sec === "number" ? st.expires_in_sec : null;
  if (exp !== null && exp <= 0) return "expired";
  return "valid";
}

export function StravaImportCard() {
  const location = useLocation();

  const [rid, setRid] = React.useState("16127771071");

  const [status, setStatus] = React.useState<StatusResp | null>(null);
  const [importRes, setImportRes] = React.useState<ImportResp | null>(null);
  const [sessions, setSessions] = React.useState<SessionListItem[] | null>(null);

  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const tokenState = getTokenState(status);

  const match =
    sessions?.find(
      (x) => String(x.session_id ?? x.ride_id ?? "") === rid.trim()
    ) ?? null;

  async function fetchStatus(): Promise<StatusResp> {
    // IMPORTANT: sets cg_uid cookie on backend origin
    return await cgApi.status();
  }

  async function fetchListAll(): Promise<SessionListItem[]> {
    return await cgApi.listAll();
  }

  async function refreshStatus() {
    setErr(null);
    try {
      const st = await fetchStatus();
      setStatus(st);
      return st;
    } catch (e: any) {
      setErr(e?.message || String(e));
      setStatus(null);
      return null;
    }
  }

  function connectStrava() {
    // One-button UX:
    // - If already valid: do nothing (button disabled anyway)
    // - Else: start OAuth, and come back to same page (next=...)
    if (tokenState === "valid") return;

    const nextRaw = `${window.location.origin}/onboarding`;
    const url = `${cgApi.baseUrl()}/api/auth/strava/login?next=${encodeURIComponent(nextRaw)}`;
    window.open(url, "_self");



  }

  // Auto-check:
  // 1) on mount
  // 2) on URL change (after OAuth redirect back, query params often change)
  React.useEffect(() => {
    refreshStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search]);

  async function onRefreshList() {
    setBusy(true);
    setErr(null);
    try {
      // ensure cookie exists + get latest status
      const st = await fetchStatus();
      setStatus(st);

      const xs = await fetchListAll();
      setSessions(xs);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onImportRide() {
    const r = rid.trim();
    if (!r) return;

    setBusy(true);
    setErr(null);
    setImportRes(null);

    try {
      // 1) status (sets cookie)
      const st = await fetchStatus();
      setStatus(st);

      // 2) require tokens
      if (st.has_tokens !== true) {
        setErr("Mangler Strava-tilkobling. Trykk Connect Strava og fullfør OAuth.");
        return;
      }

      // 3) import (backend refresh-er tokens ved behov)
      const imp = await cgApi.importRide(r);
      setImportRes(imp);

      // 4) refresh list/all
      const xs = await fetchListAll();
      setSessions(xs);

      // 5) refresh status again (oppdatert expires_in_sec)
      const st2 = await fetchStatus();
      setStatus(st2);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  const connectLabel =
    tokenState === "expired" ? "Reconnect Strava" : "Connect Strava";

  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Strava (Sprint 2)</h2>
          <p className="text-sm text-slate-600 mt-1">
            Import ride → Oppdater list/all (status hentes automatisk)
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Backend: <span className="font-mono">{cgApi.baseUrl()}</span>
          </p>
        </div>

        <button
          type="button"
          onClick={connectStrava}
          disabled={busy || tokenState === "valid"}
          className="px-3 py-2 rounded bg-slate-900 text-white text-sm hover:bg-slate-800 disabled:bg-slate-400"
          title={
            tokenState === "valid"
              ? "Strava er allerede tilkoblet"
              : "Åpner backend /login for OAuth"
          }
        >
          {tokenState === "valid" ? "Strava tilkoblet ✅" : connectLabel}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 items-center">
        <input
          value={rid}
          onChange={(e) => setRid(e.target.value)}
          className="px-3 py-2 rounded border text-sm font-mono w-[220px]"
          placeholder="ride id (rid)"
        />

        <button
          type="button"
          onClick={onImportRide}
          disabled={busy || !rid.trim()}
          className="px-3 py-2 rounded border text-sm disabled:opacity-60"
          title="POST /api/strava/import/{rid}"
        >
          {busy ? "Jobber…" : "Import ride"}
        </button>

        <button
          type="button"
          onClick={onRefreshList}
          disabled={busy}
          className="px-3 py-2 rounded border text-sm disabled:opacity-60"
          title="GET /api/sessions/list/all"
        >
          Refresh list/all
        </button>
      </div>

      <div className="mt-3 text-sm text-slate-700">
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <div>
            has_tokens: <b>{String(status?.has_tokens ?? "unknown")}</b>
          </div>
          <div>
            expires_in_sec: <b>{String(status?.expires_in_sec ?? "n/a")}</b>
          </div>
          <div>
            uid:{" "}
            <span className="font-mono text-xs">
              {String(status?.uid ?? "n/a")}
            </span>
          </div>
        </div>

        {tokenState === "expired" ? (
          <div className="mt-2 text-xs text-amber-700">
            Strava-token er utløpt. Import kan trigge refresh, ellers bruk
            Reconnect.
          </div>
        ) : null}

        {importRes ? (
          <div className="mt-2 text-xs">
            import.ok: <b>{String(importRes.ok ?? "n/a")}</b> | samples_len:{" "}
            <b>{String(importRes.samples_len ?? "n/a")}</b> | analyze.status_code:{" "}
            <b>{String(importRes.analyze?.status_code ?? "n/a")}</b>
          </div>
        ) : null}

        {sessions ? (
          <div className="mt-2 text-xs">
            list/all: <b>{sessions.length}</b>{" "}
            {match ? (
              <>
                | ✅ rid funnet | debug_source_path:{" "}
                <span className="font-mono">
                  {String(match.debug_source_path ?? "n/a")}
                </span>
              </>
            ) : (
              <>| ⚠️ rid ikke funnet enda</>
            )}
          </div>
        ) : null}

        {err ? (
          <div className="mt-2 text-xs text-red-600 whitespace-pre-wrap">
            {err}
          </div>
        ) : null}
      </div>
    </div>
  );
}
