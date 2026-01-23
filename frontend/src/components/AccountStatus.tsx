// frontend/src/components/AccountStatus.tsx
import React, { useEffect, useState } from "react";
import { cgApi, type StatusResp } from "../lib/cgApi";

function fmtDur(sec: number): string {
  const s = Math.abs(Math.trunc(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

type Origin = "mount" | "poll" | "click";

export function AccountStatus() {
  console.log("[AccountStatus] RENDER", Date.now());
  const [st, setSt] = useState<StatusResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const busyRef = React.useRef(false);

  const [tick, setTick] = useState(0);
  const [lastOrigin, setLastOrigin] = useState<Origin>("mount");
  const [lastAt, setLastAt] = useState<number | null>(null);

  async function onLogout() {
    try {
      await fetch(`${cgApi.baseUrl()}/api/auth/logout`, { method: "POST", credentials: "include" });

    } finally {
      // ✅ hard reload så AuthGateProvider må re-sjekke /api/auth/me
      window.location.assign("/login");
    }
  }

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

      // ✅ SSOT: use backend Strava status (via cgApi)
      const data = await cgApi.stravaStatus();
      console.log("[AccountStatus] stravaStatus OK", data);

      setSt(data);
      setTick((x) => x + 1);
    } catch (e: any) {
      console.error("[AccountStatus] stravaStatus FAIL", e);
      setErr(String(e?.message ?? e));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  useEffect(() => {
    let alive = true;

    (async () => {
      try {
        if (alive) await load("mount");
      } catch {
        // load() håndterer egne errors
      }
    })();

    // Viktig: poll roligere så det ikke “drukner” click-debug
    // (du kan sette tilbake til 5000 når alt funker)
    const intervalMs = 60_000;

    const t = window.setInterval(() => {
      // Ikke poll hvis vi er midt i en click/mount fetch
      if (!busyRef.current) load("poll");
    }, intervalMs);

    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, []);

  // status derived
  const hasTokens = st?.has_tokens === true;

  let expiresText: string | null = null;
  if (st && typeof st.expires_in_sec === "number") {
    if (st.expires_in_sec >= 0) expiresText = `expires in ${fmtDur(st.expires_in_sec)}`;
    else expiresText = `expired for ${fmtDur(st.expires_in_sec)}`;
  }

  return (
    <div className="relative z-50 pointer-events-auto rounded-xl border p-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="font-semibold">Account</div>

        <button
          type="button"
          onClick={onLogout}
          className="rounded-lg border px-2 py-1 text-xs pointer-events-auto relative z-50 hover:bg-slate-50"
          title="Logg ut"
        >
          Logg ut
        </button>
      </div>

      {err ? (
        <div className="mt-1 opacity-80">Status error: {err}</div>
      ) : !st ? (
        <div className="mt-1 opacity-80">Loading status…</div>
      ) : (
        <div className="mt-1 space-y-1">
          <div>
            <span className="opacity-70">uid:</span>{" "}
            <span className="font-mono">{st.uid ?? "n/a"}</span>
          </div>

          <div>
            <span className="opacity-70">has_tokens:</span>{" "}
            <span className="font-semibold">
              {st.has_tokens === true ? "true" : st.has_tokens === false ? "false" : "unknown"}
            </span>
          </div>

          <div>
            <span className="opacity-70">expires_in_sec:</span>{" "}
            <span className="font-semibold">
              {typeof st.expires_in_sec === "number" ? String(st.expires_in_sec) : "n/a"}
            </span>
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

          {hasTokens ? (
            <div className="text-xs opacity-70">Strava er tilkoblet ✅</div>
          ) : (
            <div className="text-xs opacity-70">Strava er ikke tilkoblet</div>
          )}
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
