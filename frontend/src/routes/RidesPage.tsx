// frontend/src/routes/RidesPage.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionStore } from "../state/sessionStore";
import { cgApi, type SessionListItem } from "../lib/cgApi";

const fmtNum = (n?: number | null, digits = 0): string =>
  typeof n === "number" && Number.isFinite(n) ? n.toFixed(digits) : "—";

function fmtDateOnly(input?: string | null): string {
  if (!input) return "Ukjent dato";

  // 1) YYYY-MM-DD (vanlig fra backend)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(input.trim());
  if (m) {
    const y = Number(m[1]);
    const mo = Number(m[2]) - 1;
    const d = Number(m[3]);
    const dt = new Date(y, mo, d, 12, 0, 0); // lokal midt på dagen
    return new Intl.DateTimeFormat("nb-NO", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(dt);
  }

  // 2) ISO datetime
  const t = Date.parse(input);
  if (!Number.isFinite(t)) return "Ukjent dato";

  return new Intl.DateTimeFormat("nb-NO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(t));
}

function parseTime(v?: string | null): number {
  if (!v) return -1;
  const t = Date.parse(v);
  if (Number.isFinite(t)) return t;
  // fallback for YYYY-MM-DD (should parse fine, but be safe)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);
  if (!m) return -1;
  const y = Number(m[1]);
  const mo = Number(m[2]) - 1;
  const d = Number(m[3]);
  return new Date(y, mo, d, 12, 0, 0).getTime();
}

function isEra5(src?: string | null): boolean {
  const s = (src ?? "").toLowerCase();
  return s.includes("era5");
}

function weatherBadge(src?: string | null): { label: string; tone: "good" | "warn" | "neutral" } {
  const s = (src ?? "").trim();
  if (!s) return { label: "ukjent", tone: "neutral" };
  if (isEra5(s)) return { label: "ERA5", tone: "good" };
  if (s.toLowerCase().includes("neutral")) return { label: "neutral", tone: "warn" };
  return { label: s, tone: "neutral" };
}

const Badge: React.FC<{ tone: "good" | "warn" | "neutral"; children: React.ReactNode }> = ({
  tone,
  children,
}) => {
  const cls =
    tone === "good"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : tone === "warn"
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${cls}`}>
      {children}
    </span>
  );
};

const RidesPage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionsList, loadingList, errorList, loadSessionsList } = useSessionStore();

  // Track ui profile_version + reload list når den endres (beholdt fra deg)
  const [uiProfileVersion, setUiProfileVersion] = useState<string>("");

  // DEV toggle (for console/debug)
  const [showDev, setShowDev] = useState<boolean>(false);

  // Guards
  const lastReloadKeyRef = useRef<string>("");
  const didInitRef = useRef<boolean>(false);

  // 1) Initial load
  useEffect(() => {
    loadSessionsList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2) Refresh ui profile_version
  useEffect(() => {
    let cancelled = false;

    async function refreshProfileVersion() {
      try {
        const p = await cgApi.profileGet().catch(() => null);
        const rec = p as unknown as Record<string, unknown> | null;
        const pv = String((rec?.profile_version as string | undefined) ?? "");
        if (!cancelled) setUiProfileVersion(pv);
      } catch {
        if (!cancelled) setUiProfileVersion("");
      }
    }

    void refreshProfileVersion();

    const onVis = () => {
      if (document.visibilityState === "visible") void refreshProfileVersion();
    };

    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  // 3) Når profile_version endrer seg -> reload sessions list
  useEffect(() => {
    const pv = uiProfileVersion.trim();
    if (!pv) return;

    if (!didInitRef.current) {
      didInitRef.current = true;
      lastReloadKeyRef.current = `pv::${pv}`;
      return;
    }

    const key = `pv::${pv}`;
    if (lastReloadKeyRef.current === key) return;

    lastReloadKeyRef.current = key;

    console.log("[RidesPage] profile_version changed → reloading list", { pv });
    loadSessionsList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uiProfileVersion]);

  const rows = useMemo(() => {
    const raw = (sessionsList ?? []) as SessionListItem[];
    // Sort newest first
    return [...raw].sort((a, b) => parseTime(b.start_time ?? null) - parseTime(a.start_time ?? null));
  }, [sessionsList]);

  if (loadingList) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="text-sm text-slate-500">Laster økter…</div>
      </div>
    );
  }

  if (errorList) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-3">
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm">{errorList}</div>
        <button
          type="button"
          onClick={() => loadSessionsList()}
          className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Prøv igjen
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
      <header className="flex items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">Økter</h1>
          <p className="text-sm text-slate-500">Viser {rows.length} økt(er)</p>

          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs text-slate-400">
              ui profile_version: <span className="font-mono">{uiProfileVersion || "n/a"}</span>
            </span>
            <button
              type="button"
              onClick={() => setShowDev((v) => !v)}
              className="text-xs text-slate-500 underline hover:text-slate-700"
            >
              {showDev ? "Skjul DEV" : "Vis DEV"}
            </button>
          </div>
        </div>

        <button
          type="button"
          onClick={() => loadSessionsList()}
          className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          Oppdater
        </button>
      </header>

      {rows.length === 0 ? (
        <div className="rounded-lg border bg-white p-4 text-sm text-slate-500">Ingen økter funnet.</div>
      ) : (
        <div className="space-y-3">
          {rows.map((s) => {
            const sid = String(s.session_id ?? s.ride_id ?? "");
            const wx = weatherBadge(s.weather_source ?? null);

            const distOk = typeof s.distance_km === "number" && Number.isFinite(s.distance_km);
            const wattOk =
              typeof s.precision_watt_avg === "number" && Number.isFinite(s.precision_watt_avg);

            const open = () => navigate(`/session/${sid}`, { state: { from: "rides" } });

            return (
              <div
                key={sid}
                role="button"
                tabIndex={0}
                onClick={open}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") open();
                }}
                className="group rounded-xl border bg-white p-4 hover:bg-slate-50/60 cursor-pointer"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 space-y-2">
                    {/* Headline */}
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-slate-900">
                        {fmtDateOnly(s.start_time ?? null)}
                      </div>

                      <Badge tone={wx.tone}>Vær: {wx.label}</Badge>
                      <Badge tone="neutral">Profil: {s.profile_label ?? "ukjent"}</Badge>
                    </div>

                    {/* Metrics */}
                    <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-700">
                      {distOk ? (
                        <div>
                          <span className="text-slate-500">Distance:</span>{" "}
                          <span className="font-medium text-slate-900">
                            {fmtNum(s.distance_km, 1)} km
                          </span>
                        </div>
                      ) : null}

                      <div>
                        <span className="text-slate-500">Precision Watt:</span>{" "}
                        <span className="font-medium text-slate-900">
                          {wattOk ? `${fmtNum(s.precision_watt_avg, 0)} W` : "—"}
                        </span>
                      </div>
                    </div>

                    {/* DEV details */}
                    {showDev ? (
                      <div className="mt-2 rounded-md border bg-slate-50 p-2 text-xs text-slate-600">
                        <div>
                          <span className="text-slate-500">session_id:</span>{" "}
                          <span className="font-mono">{sid}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">ride_id:</span>{" "}
                          <span className="font-mono">{String(s.ride_id ?? "")}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">weather_source:</span>{" "}
                          <span className="font-mono">{String(s.weather_source ?? "")}</span>
                        </div>
                        <div>
                          <span className="text-slate-500">start_time(raw):</span>{" "}
                          <span className="font-mono">{String(s.start_time ?? "")}</span>
                        </div>
                      </div>
                    ) : null}
                  </div>

                  {/* CTA */}
                  <div className="flex flex-col items-end gap-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        open();
                      }}
                      className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm hover:bg-white"
                    >
                      Åpne →
                    </button>
                    <div className="text-xs text-slate-400 group-hover:text-slate-500">
                      ID: <span className="font-mono">{sid}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default RidesPage;
