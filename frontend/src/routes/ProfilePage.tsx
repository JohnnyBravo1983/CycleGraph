// frontend/src/routes/ProfilePage.tsx
import { useEffect, useMemo, useState } from "react";
import { useProfileStore } from "../state/profileStore";

// ✅ MOVE 1:1 interactive model into /profile (no redesign, no backend changes)
import Interactive3DCyclistProfile from "../components/Interactive3DCyclistProfile";

/**
 * Profile Settings
 * - /profile is the single editing surface
 * - March launch: keep it simple (bike weight + rider weight)
 * - Show sensible defaults for CdA/Crr/Crank efficiency (read-only UI)
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

// ✅ Light theme components (same as onboarding)
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
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3">
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        {subtitle ? <div className="mt-1 text-xs text-slate-600">{subtitle}</div> : null}
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
        <label className="text-xs font-medium text-slate-700">
          {label} {required ? <span className="text-slate-500">*</span> : null}
        </label>
        {right}
      </div>
      {children}
    </div>
  );
}

const inputBase =
  "w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200";

function DefaultValuesBox({
  cda,
  crr,
  crankEff,
}: {
  cda: number;
  crr: number;
  crankEff: number;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="text-sm font-semibold text-slate-900">Default values</div>
      <div className="mt-1 text-xs text-slate-600">
        We’ve set sensible defaults for aerodynamic drag, rolling resistance, and drivetrain
        efficiency. Advanced, more dynamic settings will come later.
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
        <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
          <div className="text-xs font-medium text-slate-700">CdA</div>
          <div className="text-sm font-semibold text-slate-900">{cda}</div>
        </div>
        <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
          <div className="text-xs font-medium text-slate-700">Crr</div>
          <div className="text-sm font-semibold text-slate-900">{crr}</div>
        </div>
        <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
          <div className="text-xs font-medium text-slate-700">Crank efficiency</div>
          <div className="text-sm font-semibold text-slate-900">{crankEff}</div>
        </div>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const { draft, loading, error, init, setDraft, commit } = useProfileStore();
  const [saveBusy, setSaveBusy] = useState(false);

  // March launch defaults (same as onboarding)
  const DEFAULT_CDA = 0.3;
  const DEFAULT_CRR = 0.004;
  const DEFAULT_CRANK_EFF = 0.96;

  useEffect(() => {
    init();
  }, [init]);

  const d = useMemo(() => (isObj(draft) ? (draft as AnyRec) : ({} as AnyRec)), [draft]);

  // Key resolution (snake_case vs camelCase tolerance)
  const K = useMemo(() => {
    return {
      // Rider
      weight: resolveKey(d, "rider_weight_kg", ["weight_kg", "weightKg", "weight"]),

      // Bike
      bikeWeight: resolveKey(d, "bike_weight_kg", ["bikeWeightKg", "bikeWeight"]),

      // Defaults/model params (still stored, just not edited in UI now)
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

  // Ensure defaults exist (non-invasive: only fill if missing)
  useEffect(() => {
    if (!isObj(draft)) return;

    const next = { ...(draft as AnyRec) };
    const has = (k: string) => {
      const v = next[k];
      return v !== null && v !== undefined && !(typeof v === "string" && v.trim() === "");
    };

    let changed = false;

    if (!has(K.cda)) {
      next[K.cda] = DEFAULT_CDA;
      changed = true;
    }
    if (!has(K.crr)) {
      next[K.crr] = DEFAULT_CRR;
      changed = true;
    }
    if (!has(K.crankEff)) {
      next[K.crankEff] = DEFAULT_CRANK_EFF;
      changed = true;
    }
    if (!has(K.bikeWeight)) {
      next[K.bikeWeight] = 8.0;
      changed = true;
    }

    if (changed) setDraft(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, K.cda, K.crr, K.crankEff, K.bikeWeight]);

  const handleSave = async () => {
    if (saveBusy) return;
    setSaveBusy(true);
    try {
      await commit();
    } finally {
      setSaveBusy(false);
    }
  };

  if (loading) {
    return <div className="max-w-xl mx-auto p-4">Loading profile...</div>;
  }

  if (error) {
    return <div className="max-w-xl mx-auto p-4 text-red-600">{error}</div>;
  }

  return (
    <div className="mx-auto w-full max-w-6xl p-4">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 md:items-start">
        {/* LEFT: Profile form */}
        <div className="flex flex-col gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Profile Settings</h1>
            <div className="mt-1 text-sm text-slate-600">
              These values affect your FTP / PrecisionWatt modeling.
            </div>
          </div>

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
                onChange={(e) =>
                  update(K.weight, e.target.value === "" ? null : Number(e.target.value))
                }
              />
              <div className="text-[11px] text-slate-500">Required for accurate FTP modeling.</div>
            </FieldRow>
          </SectionCard>

          <SectionCard title="Bike Setup" subtitle="Used for mass modeling and climbing/acceleration.">
            <FieldRow label="Bike weight (kg)">
              <input
                className={inputBase}
                inputMode="decimal"
                placeholder="e.g. 8.2"
                value={numOrEmpty(d[K.bikeWeight])}
                onChange={(e) =>
                  update(K.bikeWeight, e.target.value === "" ? null : Number(e.target.value))
                }
              />
            </FieldRow>
          </SectionCard>

          <DefaultValuesBox cda={DEFAULT_CDA} crr={DEFAULT_CRR} crankEff={DEFAULT_CRANK_EFF} />

          <div className="flex items-center justify-end gap-3">
            <button
              onClick={handleSave}
              disabled={loading || saveBusy}
              className="px-4 py-2 rounded-md bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400"
            >
              {saveBusy ? "Saving…" : "Save Profile"}
            </button>
          </div>
        </div>

        {/* RIGHT: Interactive 3D cyclist model (as-is) */}
        <div className="md:sticky md:top-6">
          <Interactive3DCyclistProfile />
        </div>
      </div>
    </div>
  );
}

