// frontend/src/routes/ProfilePage.tsx
import { useEffect, useMemo, useState } from "react";
import { useProfileStore } from "../state/profileStore";

/**
 * Day 4: Profile Isolation
 * - /profile is the single editing surface
 * - grouped fields + tooltips
 * - optional Advanced toggle
 * - no backend/schema changes
 */

type AnyRec = Record<string, any>;

function isObj(v: unknown): v is AnyRec {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * Resolve a key name based on what exists in the current draft.
 * This makes us tolerant to snake_case vs camelCase without schema changes.
 */
function resolveKey(draft: AnyRec, preferred: string, fallbacks: string[]): string {
  if (preferred in draft) return preferred;
  for (const k of fallbacks) if (k in draft) return k;
  return preferred; // fallback to preferred if nothing exists yet
}

function numOrEmpty(v: unknown): string {
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) return v;
  return "";
}

function strOrEmpty(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function Tooltip({
  text,
  className = "",
}: {
  text: string;
  className?: string;
}) {
  return (
    <span className={`relative inline-flex items-center ${className}`}>
      <span className="group inline-flex items-center">
        <span className="ml-2 inline-flex h-5 w-5 items-center justify-center rounded-full border border-white/15 bg-white/5 text-xs text-white/80">
          i
        </span>
        <span className="pointer-events-none absolute left-0 top-6 z-20 hidden w-72 rounded-lg border border-white/10 bg-slate-900/95 p-3 text-xs text-white/90 shadow-lg group-hover:block">
          {text}
        </span>
      </span>
    </span>
  );
}

function SectionCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-sm">
      <div className="mb-3">
        <div className="text-sm font-semibold text-white/95">{title}</div>
        {subtitle ? (
          <div className="mt-1 text-xs text-white/60">{subtitle}</div>
        ) : null}
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </div>
  );
}

function FieldRow({
  label,
  required,
  right,
  children,
}: {
  label: string;
  required?: boolean;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-white/80">
          {label} {required ? <span className="text-white/60">*</span> : null}
        </label>
        {right}
      </div>
      {children}
    </div>
  );
}

const inputBase =
  "w-full rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2 text-sm text-white/90 placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-white/10";

export default function ProfilePage() {
  const { draft, loading, error, init, setDraft, commit } = useProfileStore();
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    init();
  }, [init]);

  const d = useMemo(() => (isObj(draft) ? (draft as AnyRec) : ({} as AnyRec)), [draft]);

  // Key resolution (snake_case vs camelCase tolerance)
  const K = useMemo(() => {
    return {
      weight: resolveKey(d, "weight_kg", ["weightKg", "weight", "rider_weight_kg"]),
      gender: resolveKey(d, "gender", ["sex"]),
      age: resolveKey(d, "age", ["age_years", "ageYears"]),
      country: resolveKey(d, "country", ["country_code", "countryCode"]),
      city: resolveKey(d, "city", ["town"]),
      tireWidth: resolveKey(d, "tire_width_mm", ["tireWidthMm", "tire_width", "tireWidth"]),
      cda: resolveKey(d, "cda", ["CdA", "aero_cda", "aeroCdA"]),
      crr: resolveKey(d, "crr", ["Crr", "rolling_crr", "rollingCrr"]),
      crankEff: resolveKey(d, "crank_efficiency", [
        "crankEfficiency",
        "drivetrain_efficiency",
        "drivetrainEfficiency",
      ]),
    };
  }, [d]);

  function update(key: string, value: any) {
    const next = { ...d, [key]: value };
    setDraft(next);
  }

  const handleSave = async () => {
    await commit();
  };

  if (loading) {
    return <div className="max-w-2xl mx-auto p-4">Loading profile...</div>;
  }

  if (error) {
    return <div className="max-w-2xl mx-auto p-4 text-red-600">{error}</div>;
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white/95">Profile Settings</h1>
          <div className="mt-1 text-sm text-white/60">
            These values affect your FTP / PrecisionWatt modeling.
          </div>
        </div>
      </div>

      {/* Rider Info */}
      <SectionCard
        title="Rider Info"
        subtitle="Keep this accurate — weight is the most important input."
      >
        <FieldRow label="Weight (kg)" required>
          <input
            className={inputBase}
            inputMode="decimal"
            placeholder="e.g. 78"
            value={numOrEmpty(d[K.weight])}
            onChange={(e) => update(K.weight, e.target.value === "" ? null : Number(e.target.value))}
          />
          <div className="text-[11px] text-white/40">Required for accurate FTP modeling.</div>
        </FieldRow>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <FieldRow label="Gender">
            <select
              className={inputBase}
              value={strOrEmpty(d[K.gender])}
              onChange={(e) => update(K.gender, e.target.value)}
            >
              <option value="">Prefer not to say</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </select>
          </FieldRow>

          <FieldRow label="Age">
            <input
              className={inputBase}
              inputMode="numeric"
              placeholder="e.g. 41"
              value={numOrEmpty(d[K.age])}
              onChange={(e) => update(K.age, e.target.value === "" ? null : Number(e.target.value))}
            />
          </FieldRow>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <FieldRow label="Country">
            <input
              className={inputBase}
              placeholder="e.g. Norway"
              value={strOrEmpty(d[K.country])}
              onChange={(e) => update(K.country, e.target.value)}
            />
          </FieldRow>
          <FieldRow label="City">
            <input
              className={inputBase}
              placeholder="e.g. Oslo"
              value={strOrEmpty(d[K.city])}
              onChange={(e) => update(K.city, e.target.value)}
            />
          </FieldRow>
        </div>
      </SectionCard>

      {/* Bike Setup */}
      <SectionCard title="Bike Setup" subtitle="Used to estimate rolling losses and speed.">
        <FieldRow label="Tire width (mm)">
          <input
            className={inputBase}
            inputMode="numeric"
            placeholder="e.g. 28"
            value={numOrEmpty(d[K.tireWidth])}
            onChange={(e) =>
              update(K.tireWidth, e.target.value === "" ? null : Number(e.target.value))
            }
          />
        </FieldRow>
      </SectionCard>

      {/* Aerodynamics */}
      <SectionCard title="Aerodynamics" subtitle="Used to estimate aerodynamic drag.">
        <FieldRow
          label="CdA"
          right={
            <Tooltip text='Aerodynamic drag coefficient (0.250–0.350, lower = faster). Affects FTP modeling.' />
          }
        >
          <input
            className={inputBase}
            inputMode="decimal"
            placeholder="e.g. 0.300"
            value={numOrEmpty(d[K.cda])}
            onChange={(e) => update(K.cda, e.target.value === "" ? null : Number(e.target.value))}
          />
        </FieldRow>
      </SectionCard>

      {/* Advanced */}
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-sm">
        <button
          type="button"
          onClick={() => setShowAdvanced((s) => !s)}
          className="w-full text-left"
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-white/95">Advanced settings</div>
              <div className="mt-1 text-xs text-white/60">
                Optional — you can leave these as defaults.
              </div>
            </div>
            <div className="text-xs text-white/70">{showAdvanced ? "Hide" : "Show"}</div>
          </div>
        </button>

        {showAdvanced ? (
          <div className="mt-4 flex flex-col gap-3">
            <FieldRow
              label="Crr"
              right={
                <Tooltip text='Rolling resistance (0.0030–0.0050, lower = faster). Affects FTP modeling.' />
              }
            >
              <input
                className={inputBase}
                inputMode="decimal"
                placeholder="e.g. 0.0040"
                value={numOrEmpty(d[K.crr])}
                onChange={(e) => update(K.crr, e.target.value === "" ? null : Number(e.target.value))}
              />
            </FieldRow>

            <FieldRow
              label="Crank efficiency"
              right={
                <Tooltip text='Power transfer efficiency (typically 96%). Affects FTP modeling.' />
              }
            >
              <input
                className={inputBase}
                inputMode="decimal"
                placeholder="e.g. 0.96"
                value={numOrEmpty(d[K.crankEff])}
                onChange={(e) =>
                  update(K.crankEff, e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </FieldRow>
          </div>
        ) : null}
      </div>

      {/* Save */}
      <div className="flex items-center justify-end gap-3">
        <button
          onClick={handleSave}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400"
        >
          Save Profile
        </button>
      </div>
    </div>
  );
}
