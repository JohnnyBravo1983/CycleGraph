// frontend/src/components/Profile/ProfilePeekCard.tsx
import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import { useProfileStore } from "../../state/profileStore";

function fmtNumber(v: unknown, suffix = ""): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  return `${n}${suffix}`;
}

function fmtPercent(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "—";
  // 0.96 -> 96%, 96 -> 96%
  const pct = n <= 1 ? n * 100 : n;
  return `${Math.round(pct)}%`;
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
  const { draft, loading, error, init } = useProfileStore();

  useEffect(() => {
    void init(); // load profile into store (SSOT)
  }, [init]);

  const weight = (draft as any)?.rider_weight_kg ?? null;
  const bikeWeight = (draft as any)?.bike_weight_kg ?? null;

  const cda = (draft as any)?.cda ?? null;
  const crr = (draft as any)?.crr ?? null;

  const crankEff = (draft as any)?.crank_efficiency ?? null;
  const crankEffPct = (draft as any)?.crank_eff_pct ?? null;

  const tire = (draft as any)?.tire_width_mm ?? null;

  // optional / might not exist in draft/backend -> keep as display-only
  const ftp = (draft as any)?.ftp_watts ?? null;

  // Display-only defaults (do NOT write/save anything)
  const displayCrank =
    crankEff != null
      ? fmtPercent(crankEff)
      : crankEffPct != null
      ? fmtPercent(crankEffPct)
      : "96%";

  return (
    <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-lg font-bold text-slate-900">Key Profile Metrics</div>
          <div className="text-sm text-slate-600">Read-only. Edit everything in Profile Settings.</div>
        </div>

        <Link
          to="/profile"
          className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition shrink-0"
        >
          Edit Profile
        </Link>
      </div>

      <div className="mt-4">
        {loading ? <div className="text-sm text-slate-600">Loading profile…</div> : null}

        {!loading && error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {error}
          </div>
        ) : null}

        {!loading && !error ? (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <Row label="FTP (modeled)" value={ftp != null ? fmtNumber(ftp, " W") : "—"} />
            <Row label="Rider weight" value={fmtNumber(weight, " kg")} />
            <Row label="Bike weight" value={fmtNumber(bikeWeight, " kg")} />
            <Row label="CdA" value={fmtNumber(cda)} />
            <Row label="Crr" value={fmtNumber(crr)} />
            <Row label="Crank efficiency" value={displayCrank} />
            <Row label="Tire width" value={fmtNumber(tire, " mm")} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
