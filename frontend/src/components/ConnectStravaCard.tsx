import React from "react";
import { cgApi, StatusResp } from "../lib/cgApi";

export function ConnectStravaCard() {
  const [status, setStatus] = React.useState<StatusResp | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  async function checkStatus() {
    setBusy(true);
    setErr(null);
    try {
      const s = await cgApi.status(); // IMPORTANT: sets cg_uid cookie
      setStatus(s);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  function connect() {
    // open in same tab so callback lands cleanly
    window.open(`${cgApi.baseUrl()}/login`, "_self");
  }

  const hasTokens = status?.has_tokens === true;

  return (
    <div style={{ border: "1px solid #333", borderRadius: 10, padding: 12, marginTop: 16 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>Koble til Strava</div>

      <div style={{ fontSize: 12, opacity: 0.85, marginBottom: 10 }}>
        Vi bruker Strava for å hente turer og bygge din første analyse. <br />
        Backend: <span style={{ fontFamily: "monospace" }}>{cgApi.baseUrl()}</span>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button onClick={checkStatus} disabled={busy}>
          {busy ? "Sjekker…" : "Check status"}
        </button>

        <button onClick={connect} disabled={busy}>
          Connect Strava
        </button>
      </div>

      <div style={{ marginTop: 10, fontSize: 12 }}>
        status.has_tokens: <b>{String(status?.has_tokens ?? "unknown")}</b>{" "}
        | expires_in_sec: <b>{String(status?.expires_in_sec ?? "n/a")}</b>
      </div>

      {!hasTokens && status && (
        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.9 }}>
          Tips: Trykk <b>Connect Strava</b>, fullfør login, gå tilbake hit og trykk <b>Check status</b>.
        </div>
      )}

      {err && <div style={{ marginTop: 10, color: "#ff6b6b", whiteSpace: "pre-wrap" }}>{err}</div>}
    </div>
  );
}
