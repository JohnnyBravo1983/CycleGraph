// frontend/src/routes/ProfilePage.tsx
import { useEffect, useMemo, useState } from "react";
import { useProfileStore } from "../state/profileStore";
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

const inputBase =
  "w-full rounded-lg border-2 border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all";

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
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
        <div className="text-slate-600">Loading profile...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
        <div className="text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-8">
      <div className="max-w-7xl mx-auto px-4">
        {/* Interactive 3D Component - Full Width on Desktop, Stack on Mobile */}
        <div className="mb-6">
          <Interactive3DCyclistProfile />
        </div>

        {/* Editable Fields Card - Positioned Below Model */}
        <div className="max-w-2xl mx-auto">
          <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-6 shadow-[0_20px_60px_rgba(0,0,0,0.15)] border border-slate-200">
            <div className="mb-6">
              <h3 className="text-lg font-bold text-slate-900 mb-1">Your Profile Data</h3>
              <p className="text-sm text-slate-600">
                Update your actual weight and bike specs. These values feed into the physics model above.
              </p>
            </div>

            <div className="space-y-5">
              {/* Rider Weight */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Rider Weight (kg) <span className="text-red-500">*</span>
                </label>
                <input
                  className={inputBase}
                  inputMode="decimal"
                  placeholder="e.g. 75"
                  value={numOrEmpty(d[K.weight])}
                  onChange={(e) =>
                    update(K.weight, e.target.value === "" ? null : Number(e.target.value))
                  }
                />
                <p className="mt-1.5 text-xs text-slate-500">
                  Critical for accurate FTP modeling and climbing power calculations.
                </p>
              </div>

              {/* Bike Weight */}
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Bike Weight (kg)
                </label>
                <input
                  className={inputBase}
                  inputMode="decimal"
                  placeholder="e.g. 8.0"
                  value={numOrEmpty(d[K.bikeWeight])}
                  onChange={(e) =>
                    update(K.bikeWeight, e.target.value === "" ? null : Number(e.target.value))
                  }
                />
                <p className="mt-1.5 text-xs text-slate-500">
                  Used for total system mass in climbing and acceleration modeling.
                </p>
              </div>

              {/* Default Values Info Box */}
              <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border-2 border-slate-200 p-4">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex-shrink-0">
                    <svg
                      className="w-5 h-5 text-slate-600"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-slate-900 mb-2">
                      Advanced Parameters
                    </div>
                    <p className="text-xs text-slate-600 mb-3 leading-relaxed">
                      We've set sensible defaults for CdA, Crr, and drivetrain efficiency. More
                      granular controls coming in future updates.
                    </p>
                    <div className="grid grid-cols-3 gap-3">
                      <div className="text-center">
                        <div className="text-xs font-medium text-slate-500 mb-1">CdA</div>
                        <div className="text-sm font-bold text-slate-900">{DEFAULT_CDA}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-xs font-medium text-slate-500 mb-1">Crr</div>
                        <div className="text-sm font-bold text-slate-900">{DEFAULT_CRR}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-xs font-medium text-slate-500 mb-1">Efficiency</div>
                        <div className="text-sm font-bold text-slate-900">
                          {(DEFAULT_CRANK_EFF * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Save Button */}
            <div className="mt-6 pt-5 border-t border-slate-200">
              <button
                onClick={handleSave}
                disabled={loading || saveBusy}
                className="w-full rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-6 py-3.5 text-sm font-bold text-white shadow-lg hover:shadow-xl hover:scale-[1.01] transition-all duration-200 disabled:from-slate-400 disabled:to-slate-500 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center justify-center gap-2"
              >
                {saveBusy ? (
                  <>
                    <svg
                      className="animate-spin h-5 w-5"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Saving...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.5}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    Save Profile Changes
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
