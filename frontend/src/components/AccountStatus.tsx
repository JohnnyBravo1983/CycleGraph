import React from "react";
import { fetchStatus, tokenState, type StatusResp } from "../lib/statusApi";

function fmtDur(sec: number): string {
  const s = Math.abs(Math.trunc(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

type Origin = "mount" | "poll" | "click";

export function AccountStatus() {
  const [st, setSt] = React.useState<StatusResp | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  const [busy, setBusy] = React.useState(false);
  const busyRef = React.useRef(false);

  const [tick, setTick] = React.useState(0);
  const [lastOrigin, setLastOrigin] = React.useState<Origin>("mount");
  const [lastAt, setLastAt] = React.useState<number | null>(null);

  async function load(origin: Origin) {
    // Guard: ikke start ny hvis vi allerede er i flight
    if (busyRef.current) {
      console.log("[AccountStatus] load() SKIP (busy)", { origin, t: Date.now() });
      return;
    }

    console.log("[AccountStatus] load()", { origin, t: Date.now() });

    busyRef.current = true;
    setBusy(true);
    setLastOrigin(origin);
    setLastAt(Date.now());

    try {
      setErr(null);
      const data = await fetchStatus();
      console.log("[AccountStatus] fetchStatus OK", data);
      setSt(data);
      setTick((x) => x + 1);
    } catch (e: any) {
      console.error("[AccountStatus] fetchStatus FAIL", e);
      setErr(e?.message ?? String(e));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  React.useEffect(() => {
    load("mount");

    // Viktig: poll roligere så det ikke “drukner” click-debug
    // (du kan sette tilbake til 5000 når alt funker)
    const intervalMs = 60_000;

    const t = window.setInterval(() => {
      // Ikke poll hvis vi er midt i en click/mount fetch
      if (!busyRef.current) load("poll");
    }, intervalMs);

    return () => window.clearInterval(t);
  }, []);

  const state = tokenState(st);

  let expiresText: string | null = null;
  if (st && typeof st.expires_in_sec === "number") {
    if (st.expires_in_sec >= 0) expiresText = `expires in ${fmtDur(st.expires_in_sec)}`;
    else expiresText = `expired for ${fmtDur(st.expires_in_sec)}`;
  }

  return (
    <div className="relative z-50 pointer-events-auto rounded-xl border p-3 text-sm">
      <div className="font-semibold">Account</div>

      {err ? (
        <div className="mt-1 opacity-80">Status error: {err}</div>
      ) : !st ? (
        <div className="mt-1 opacity-80">Loading status…</div>
      ) : (
        <div className="mt-1 space-y-1">
          <div>
            <span className="opacity-70">uid:</span>{" "}
            <span className="font-mono">{st.uid}</span>
          </div>
          <div>
            <span className="opacity-70">token:</span>{" "}
            <span className="font-medium">{state}</span>
            {expiresText ? <span className="opacity-70"> ({expiresText})</span> : null}
          </div>
          <div className="opacity-60">
            tick: {tick}
            {lastAt ? (
              <>
                {" "}
                • last: <span className="font-mono">{lastOrigin}</span>{" "}
                <span className="font-mono">{new Date(lastAt).toLocaleTimeString()}</span>
              </>
            ) : null}
          </div>
        </div>
      )}

      <button
        className="mt-2 rounded-lg border px-2 py-1 text-xs pointer-events-auto relative z-50"
        type="button"
        disabled={busy}
        onPointerDownCapture={(e) => {
          // Dette avslører 100% om klikket faktisk når React
          console.log("[AccountStatus] POINTER DOWN (capture)", Date.now(), e.target);
        }}
        onClick={(e) => {
          console.log("[AccountStatus] BUTTON CLICK", Date.now(), e.target);
          e.preventDefault();
          e.stopPropagation();
          load("click");
        }}
      >
        {busy ? "Refreshing…" : "Refresh"}
      </button>
    </div>
  );
}
