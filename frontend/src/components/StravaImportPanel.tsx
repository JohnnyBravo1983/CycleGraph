import React from "react";
import {
  cgApi,
  type ImportResp,
  type SessionListItem,
  type StatusResp,
} from "../lib/cgApi";

function getErrMsg(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

export function StravaImportPanel() {
  const [rid, setRid] = React.useState("16127771071");
  const [status, setStatus] = React.useState<StatusResp | null>(null);
  const [importRes, setImportRes] = React.useState<ImportResp | null>(null);
  const [sessions, setSessions] = React.useState<SessionListItem[] | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  async function refreshStatus() {
    setErr(null);
    const s = await cgApi.status();
    setStatus(s);
    return s;
  }

  async function refreshList() {
    setErr(null);
    const xs = await cgApi.listAll();
    setSessions(xs);
    return xs;
  }

  async function doImport() {
    setBusy(true);
    setErr(null);
    setImportRes(null);
    try {
      const s = await refreshStatus(); // sets cg_uid cookie

      if (!s?.has_tokens) {
        setErr("Mangler Strava-tilkobling. Trykk 'Connect Strava' og fullfør login.");
        return;
      }

      const r = await cgApi.importRide(rid.trim());
      setImportRes(r);

      await refreshList();
    } catch (e: unknown) {
      setErr(getErrMsg(e));
    } finally {
      setBusy(false);
    }
  }

  const match =
    sessions?.find(
      (x) => String(x.session_id ?? x.ride_id ?? "") === rid.trim()
    ) ?? null;

  return (
    <div
      style={{
        border: "1px solid #333",
        borderRadius: 8,
        padding: 12,
        marginBottom: 16,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ fontWeight: 700 }}>
            Sprint 2 – Strava Import (Dev Panel)
          </div>
          <div style={{ opacity: 0.8, fontSize: 12 }}>
            Backend: {cgApi.baseUrl()} (credentials: include)
          </div>
        </div>

        {/* PATCH: send med ?next= slik at backend redirecter tilbake hit */}
        <button
          onClick={() => {
            const next = encodeURIComponent(window.location.href);
            window.open(`${cgApi.baseUrl()}/login?next=${next}`, "_self");
          }}
          disabled={busy}
        >
          Connect Strava
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        <input
          value={rid}
          onChange={(e) => setRid(e.target.value)}
          style={{ padding: 8, minWidth: 220 }}
        />
        <button
          onClick={() =>
            refreshStatus().catch((e: unknown) => setErr(getErrMsg(e)))
          }
          disabled={busy}
        >
          Check status
        </button>
        <button onClick={doImport} disabled={busy || !rid.trim()}>
          {busy ? "Importing…" : "Import from Strava"}
        </button>
        <button
          onClick={() =>
            refreshList().catch((e: unknown) => setErr(getErrMsg(e)))
          }
          disabled={busy}
        >
          Refresh list/all
        </button>
      </div>

      {err && (
        <div
          style={{
            marginTop: 10,
            color: "#ff6b6b",
            whiteSpace: "pre-wrap",
          }}
        >
          {err}
        </div>
      )}

      <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
        <div style={{ fontSize: 12, opacity: 0.9 }}>
          status.has_tokens: <b>{String(status?.has_tokens ?? "unknown")}</b> |
          expires_in_sec:{" "}
          <b>{String(status?.expires_in_sec ?? "n/a")}</b> | uid:{" "}
          <b>{String(status?.uid ?? "n/a")}</b>
        </div>

        {importRes && (
          <div style={{ fontSize: 12 }}>
            import.ok: <b>{String(importRes.ok ?? "n/a")}</b> | samples_len:{" "}
            <b>{String(importRes.samples_len ?? "n/a")}</b> |
            analyze.status_code:{" "}
            <b>{String(importRes.analyze?.status_code ?? "n/a")}</b>
          </div>
        )}

        {sessions && (
          <div style={{ fontSize: 12 }}>
            list/all: <b>{sessions.length}</b> sessions{" "}
            {match ? (
              <>
                | ✅ rid funnet | debug_source_path:{" "}
                <span style={{ fontFamily: "monospace" }}>
                  {String(match.debug_source_path ?? "n/a")}
                </span>
              </>
            ) : (
              <>| ⚠️ rid ikke funnet i listen enda</>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
