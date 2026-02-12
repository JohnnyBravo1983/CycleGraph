import React from "react";
import { Link } from "react-router-dom";
import { getProfile } from "../../api/profile";

type ProfileData = {
  rider_weight_kg?: number | null;
  bike_weight_kg?: number | null;
  cda?: number | null;
  crr?: number | null;
  crank_efficiency?: number | null; // 0-1 eller 0-100
  bike_type?: string | null;
  tire_width_mm?: number | null;
  tire_quality?: string | null;
  ftp_watts?: number | null;
  profile_version?: number | null;
};

function fmtNumber(v: any, suffix = ""): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return `${n}${suffix}`;
}
function fmtPercent(v: any): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  const pct = n <= 1 ? n * 100 : n;
  return `${pct.toFixed(0)}%`;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6 border-b border-slate-100 py-2.5 last:border-b-0">
      <div className="text-sm text-slate-600">{label}</div>
      <div className="text-sm font-semibold text-slate-900 text-right">{value}</div>
    </div>
  );
}

export default function ProfilePeekCard() {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [profile, setProfile] = React.useState<ProfileData | null>(null);

  const [open, setOpen] = React.useState(false);
  const wrapRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getProfile();
        if (!alive) return;
        setProfile(data as any);
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message || "Kunne ikke hente profilen.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // Close popover on outside click / escape
  React.useEffect(() => {
    function onDocDown(ev: MouseEvent | TouchEvent) {
      const el = wrapRef.current;
      if (!el) return;
      if (!el.contains(ev.target as Node)) setOpen(false);
    }
    function onKey(ev: KeyboardEvent) {
      if (ev.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocDown);
    document.addEventListener("touchstart", onDocDown, { passive: true });
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocDown);
      document.removeEventListener("touchstart", onDocDown);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const subtitle = "Rytter- og sykkeldata (kun visning)";

  return (
    <div ref={wrapRef} className="relative">
      {/* Compact card */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="w-full text-left rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40 hover:shadow-[0_24px_70px_rgba(0,0,0,0.28)] transition"
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <div className="flex items-start justify-between gap-6">
          <div>
            <div className="text-lg font-bold text-slate-900">Profile</div>
            <div className="text-sm text-slate-600">{subtitle}</div>
            <div className="mt-2 text-xs text-slate-500">
              {loading
                ? "Laster …"
                : error
                ? "Kunne ikke hente profil"
                : profile
                ? "Hover / klikk for detaljer"
                : "Ingen profil ennå"}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {!loading && !error && profile && (
              <div className="text-xs font-semibold text-slate-700 bg-slate-100 px-3 py-1.5 rounded-full">
                v{profile.profile_version ?? "—"}
              </div>
            )}
            <div className="text-slate-400 text-sm">▾</div>
          </div>
        </div>
      </button>

      {/* Popover */}
      {open && (
        <div
          className="absolute z-20 mt-3 w-full rounded-2xl border border-slate-200 bg-white shadow-[0_20px_60px_rgba(0,0,0,0.20)] p-4"
          role="dialog"
          aria-label="Profil-detaljer"
        >
          {loading && <div className="text-sm text-slate-600">Laster profil …</div>}

          {!loading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              {error}
            </div>
          )}

          {!loading && !error && !profile && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
              <div className="text-sm font-semibold text-slate-900">Ingen profil ennå</div>
              <div className="mt-1 text-sm text-slate-600">
                Fullfør onboarding for å sette opp profilen din.
              </div>
              <div className="mt-4">
                <Link
                  to="/onboarding"
                  className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 transition"
                >
                  Gå til onboarding
                </Link>
              </div>
            </div>
          )}

          {!loading && !error && profile && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <Row label="Rider weight" value={fmtNumber(profile.rider_weight_kg, " kg")} />
              <Row label="Bike weight" value={fmtNumber(profile.bike_weight_kg, " kg")} />
              <Row label="CdA" value={fmtNumber(profile.cda)} />
              <Row label="Crr" value={fmtNumber(profile.crr)} />
              <Row label="Crank efficiency" value={fmtPercent(profile.crank_efficiency)} />
              <Row label="Bike type" value={profile.bike_type || "—"} />
              <Row label="Tire width" value={fmtNumber(profile.tire_width_mm, " mm")} />
              <Row label="Tire quality" value={profile.tire_quality || "—"} />
              <Row
                label="FTP"
                value={
                  profile.ftp_watts === null || profile.ftp_watts === undefined
                    ? "Not set"
                    : `${profile.ftp_watts} W`
                }
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
