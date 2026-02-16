// frontend/src/components/ProfileForm.tsx
import React from "react";

type ProfileDraft = {
  rider_weight_kg?: number | null;

  // ✅ ensure present
  bike_weight_kg?: number | null;

  // Aerodynamics / rolling
  cda?: number | null;
  crr?: number | null;

  // Crank
  crank_efficiency?: number | null;
  crank_eff_pct?: number | null;

  // Bike / tires
  bike_type?: string | null;
  tire_width_mm?: number | null;
  tire_quality?: string | null;

  device?: string | null;
  [k: string]: unknown;
};

type Props = {
  value: ProfileDraft;
  onChange: (patch: Partial<ProfileDraft>) => void; // <-- patch-style (Zustand-friendly)
  disabled?: boolean;
};

// ---------- helpers: never feed <input value={null/undefined}> ----------
const numToStr = (v: unknown): string =>
  typeof v === "number" && Number.isFinite(v) ? String(v) : "";

const strToNumOrNull = (raw: string): number | null => {
  const s = raw.trim();
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};

export default function ProfileForm({ value, onChange, disabled }: Props) {
  const setNum =
    (key: keyof ProfileDraft) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = strToNumOrNull(e.target.value);
      onChange({ [key]: next } as Partial<ProfileDraft>);
    };

  const setStr =
    (key: keyof ProfileDraft) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const v = e.target.value;
      onChange({ [key]: v === "" ? null : v } as Partial<ProfileDraft>);
    };

  const Tip = ({ text }: { text: string }) => (
    <span className="relative inline-flex items-center">
      <span className="group inline-flex items-center">
        <span className="ml-2 inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-xs text-slate-700">
          i
        </span>
        <span className="pointer-events-none absolute left-0 top-6 z-20 hidden w-72 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700 shadow-lg group-hover:block">
          {text}
        </span>
      </span>
    </span>
  );

  const Card = ({
    title,
    subtitle,
    children,
  }: {
    title: string;
    subtitle?: string;
    children: React.ReactNode;
  }) => (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-3">
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        {subtitle ? <div className="mt-1 text-xs text-slate-600">{subtitle}</div> : null}
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );

  const inputBase =
    "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-slate-200 disabled:opacity-60";

  return (
    <div className="space-y-4">
      {/* Rider */}
      <Card title="Rider info" subtitle="Baseline numbers for the physics model.">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700">Rider weight (kg)</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={numToStr(value?.rider_weight_kg)}
              onChange={setNum("rider_weight_kg")}
              disabled={disabled}
              className={inputBase}
              placeholder="e.g. 83"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700">Device</span>
            <input
              type="text"
              value={typeof value?.device === "string" ? value.device : ""}
              onChange={setStr("device")}
              disabled={disabled}
              className={inputBase}
              placeholder="strava"
            />
          </label>
        </div>

        {/* ✅ Patch: Country/City block removed (if it existed) */}
      </Card>

      {/* Bike */}
      <Card title="Bike setup" subtitle="Used for rolling resistance and mass modeling.">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700">Bike type</span>
            <select
              value={typeof value?.bike_type === "string" ? value.bike_type : ""}
              onChange={setStr("bike_type")}
              disabled={disabled}
              className={inputBase}
            >
              <option value="">—</option>
              <option value="road">road</option>
              <option value="tt">tt</option>
              <option value="gravel">gravel</option>
              <option value="mtb">mtb</option>
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700">Bike weight (kg)</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={numToStr(value?.bike_weight_kg)}
              onChange={setNum("bike_weight_kg")}
              disabled={disabled}
              className={inputBase}
              placeholder="e.g. 8.2"
            />
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700">Tire width</span>
            <select
              value={String(
                typeof value?.tire_width_mm === "number" && Number.isFinite(value.tire_width_mm)
                  ? value.tire_width_mm
                  : 28
              )}
              onChange={(e) => onChange({ tire_width_mm: Number(e.target.value) })}
              disabled={disabled}
              className={inputBase}
            >
              <option value="25">25mm</option>
              <option value="28">28mm</option>
              <option value="31">30–32mm</option>
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700">Tire quality</span>
            <select
              value={typeof value?.tire_quality === "string" ? value.tire_quality : ""}
              onChange={setStr("tire_quality")}
              disabled={disabled}
              className={inputBase}
            >
              <option value="">—</option>
              <option value="budget">budget</option>
              <option value="training">training</option>
              <option value="performance">performance</option>
              <option value="race">race</option>
            </select>
          </label>
        </div>
      </Card>

      {/* Aerodynamics */}
      <Card title="Aerodynamics" subtitle="Affects drag and high-speed power estimation.">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700 flex items-center">
              CdA
              <Tip text="Aerodynamic drag coefficient (0.250–0.350). Lower = faster." />
            </span>
            <input
              type="number"
              inputMode="decimal"
              step="0.001"
              value={numToStr(value?.cda)}
              onChange={setNum("cda")}
              disabled={disabled}
              className={inputBase}
              placeholder="e.g. 0.300"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700 flex items-center">
              Crr
              <Tip text="Rolling resistance (0.0030–0.0050). Lower = faster." />
            </span>
            <input
              type="number"
              inputMode="decimal"
              step="0.0001"
              value={numToStr(value?.crr)}
              onChange={setNum("crr")}
              disabled={disabled}
              className={inputBase}
              placeholder="e.g. 0.0040"
            />
          </label>
        </div>
      </Card>

      {/* Advanced */}
      <Card title="Advanced settings" subtitle="Optional. Only change if you know what you’re doing.">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700 flex items-center">
              Crank efficiency (0–1)
              <Tip text="Power transfer efficiency (typically ~96%). Impacts modeled power/FTP." />
            </span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              value={numToStr(value?.crank_efficiency)}
              onChange={setNum("crank_efficiency")}
              disabled={disabled}
              className={inputBase}
              placeholder="e.g. 0.96"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-700">Crank efficiency (%)</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={numToStr(value?.crank_eff_pct)}
              onChange={setNum("crank_eff_pct")}
              disabled={disabled}
              className={inputBase}
              placeholder="e.g. 96"
            />
          </label>
        </div>
      </Card>
    </div>
  );
}
