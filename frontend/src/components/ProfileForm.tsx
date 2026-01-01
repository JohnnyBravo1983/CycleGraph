import React from "react";

type ProfileDraft = {
  rider_weight_kg?: number | null;
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
  const setNum = (key: keyof ProfileDraft) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = strToNumOrNull(e.target.value);
    onChange({ [key]: next } as Partial<ProfileDraft>);
  };

  const setStr = (key: keyof ProfileDraft) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const v = e.target.value;
    onChange({ [key]: v === "" ? null : v } as Partial<ProfileDraft>);
  };

  return (
    <div className="space-y-4">
      {/* Weight */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Rider weight (kg)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            value={numToStr(value?.rider_weight_kg)}
            onChange={setNum("rider_weight_kg")}
            disabled={disabled}
            className="px-3 py-2 rounded border"
            placeholder="e.g. 83"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Bike weight (kg)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            value={numToStr(value?.bike_weight_kg)}
            onChange={setNum("bike_weight_kg")}
            disabled={disabled}
            className="px-3 py-2 rounded border"
            placeholder="e.g. 8"
          />
        </label>
      </div>

      {/* Aero / rolling */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">CdA</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.001"
            value={numToStr(value?.cda)}
            onChange={setNum("cda")}
            disabled={disabled}
            className="px-3 py-2 rounded border"
            placeholder="e.g. 0.300"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Crr</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.0001"
            value={numToStr(value?.crr)}
            onChange={setNum("crr")}
            disabled={disabled}
            className="px-3 py-2 rounded border"
            placeholder="e.g. 0.0040"
          />
        </label>
      </div>

      {/* Crank */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Crank efficiency (0-1)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.01"
            value={numToStr(value?.crank_efficiency)}
            onChange={setNum("crank_efficiency")}
            disabled={disabled}
            className="px-3 py-2 rounded border"
            placeholder="e.g. 0.96"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Crank efficiency (%)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            value={numToStr(value?.crank_eff_pct)}
            onChange={setNum("crank_eff_pct")}
            disabled={disabled}
            className="px-3 py-2 rounded border"
            placeholder="e.g. 96"
          />
        </label>
      </div>

      {/* Bike / tires */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Bike type</span>
          <select
            value={typeof value?.bike_type === "string" ? value.bike_type : ""}
            onChange={setStr("bike_type")}
            disabled={disabled}
            className="px-3 py-2 rounded border bg-white"
          >
            <option value="">—</option>
            <option value="road">road</option>
            <option value="tt">tt</option>
            <option value="gravel">gravel</option>
            <option value="mtb">mtb</option>
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Tire width (mm)</span>
          <input
            type="number"
            inputMode="numeric"
            step="1"
            value={numToStr(value?.tire_width_mm)}
            onChange={setNum("tire_width_mm")}
            disabled={disabled}
            className="px-3 py-2 rounded border"
            placeholder="e.g. 28"
          />
        </label>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Tire quality</span>
          <select
            value={typeof value?.tire_quality === "string" ? value.tire_quality : ""}
            onChange={setStr("tire_quality")}
            disabled={disabled}
            className="px-3 py-2 rounded border bg-white"
          >
            <option value="">—</option>
            <option value="budget">budget</option>
            <option value="training">training</option>
            <option value="performance">performance</option>
            <option value="race">race</option>
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-slate-700">Device</span>
          <input
            type="text"
            value={typeof value?.device === "string" ? value.device : ""}
            onChange={setStr("device")}
            disabled={disabled}
            className="px-3 py-2 rounded border"
            placeholder="strava"
          />
        </label>
      </div>
    </div>
  );
}
