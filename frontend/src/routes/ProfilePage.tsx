// frontend/src/routes/ProfilePage.tsx
import { useEffect, useMemo, useState } from "react";
import { useProfileStore } from "../state/profileStore";

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
  if (typeof v === "string" && v.trim() !== "") return v;
  return "";
}

const inputBase =
  "w-full rounded-lg border-2 border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all duration-200";

export default function ProfilePage() {
  const { draft, loading, error, init, setDraft, commit } = useProfileStore();
  const [saveBusy, setSaveBusy] = useState(false);
  const [hoveredParam, setHoveredParam] = useState<string | null>(null);

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

  // Handle decimal input for weight fields
  const handleWeightChange = (key: string, value: string) => {
    if (value === "") {
      update(key, null);
      return;
    }
    
    // Allow decimal input
    const numValue = parseFloat(value);
    if (!isNaN(numValue)) {
      update(key, numValue);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 flex items-center justify-center">
        <div className="flex items-center gap-3">
          <svg
            className="animate-spin h-6 w-6 text-emerald-600"
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
          <span className="text-slate-600 font-medium">Loading profile...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 flex items-center justify-center">
        <div className="max-w-md rounded-xl bg-red-50 border-2 border-red-200 p-6">
          <div className="flex items-start gap-3">
            <svg
              className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <div className="font-semibold text-red-900 mb-1">Error loading profile</div>
              <div className="text-sm text-red-700">{error}</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Profile Settings</h1>
          <p className="text-slate-600">
            These values affect your FTP and power modeling accuracy. Keep them up to date for best
            results.
          </p>
        </div>

        {/* Main Card */}
        <div className="rounded-2xl bg-white shadow-xl border border-slate-200 overflow-hidden">
          {/* Card Header */}
          <div className="bg-gradient-to-r from-emerald-500 to-emerald-600 px-6 py-4">
            <div className="flex items-center gap-2 text-white">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
              <h2 className="font-semibold">Your Profile Data</h2>
            </div>
          </div>

          {/* Card Body */}
          <div className="p-6 space-y-6">
            {/* Rider Weight */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">
                Rider Weight (kg) <span className="text-red-500">*</span>
              </label>
              <input
                className={inputBase}
                type="text"
                inputMode="decimal"
                placeholder="e.g. 75.5"
                value={numOrEmpty(d[K.weight])}
                onChange={(e) => handleWeightChange(K.weight, e.target.value)}
              />
              <div className="mt-2 flex items-start gap-2 text-xs text-slate-600">
                <svg
                  className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5"
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
                <span>
                  Required for accurate FTP modeling and climbing power calculations. This is the
                  most important input.
                </span>
              </div>
            </div>

            {/* Bike Weight */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">
                Bike Weight (kg)
              </label>
              <input
                className={inputBase}
                type="text"
                inputMode="decimal"
                placeholder="e.g. 8.2"
                value={numOrEmpty(d[K.bikeWeight])}
                onChange={(e) => handleWeightChange(K.bikeWeight, e.target.value)}
              />
              <div className="mt-2 flex items-start gap-2 text-xs text-slate-600">
                <svg
                  className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5"
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
                <span>
                  Used for total system mass in climbing and acceleration modeling. Typical road
                  bikes: 7-9 kg.
                </span>
              </div>
            </div>

            {/* Advanced Parameters Section */}
            <div className="pt-6 border-t-2 border-slate-100">
              <div className="rounded-xl bg-gradient-to-br from-slate-50 to-slate-100 border-2 border-slate-200 p-5">
                <div className="flex items-start gap-3 mb-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-slate-200 flex items-center justify-center">
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
                        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-bold text-slate-900 mb-1">
                      Advanced Parameters
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      We've set sensible defaults for aerodynamic drag, rolling resistance, and
                      drivetrain efficiency. Hover over each to learn more.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  {/* CdA */}
                  <div 
                    className="relative bg-white rounded-lg border border-slate-200 p-3 text-center cursor-help transition-all hover:border-emerald-400 hover:shadow-md"
                    onMouseEnter={() => setHoveredParam('cda')}
                    onMouseLeave={() => setHoveredParam(null)}
                  >
                    <div className="text-xs font-medium text-slate-500 mb-1">CdA</div>
                    <div className="text-lg font-bold text-slate-900">{DEFAULT_CDA}</div>
                    <div className="text-[10px] text-slate-500 mt-1">Drag area</div>
                    
                    {/* Tooltip */}
                    {hoveredParam === 'cda' && (
                      <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-900 text-white text-xs rounded-lg shadow-xl">
                        <div className="font-semibold mb-1">Coefficient of Drag Area</div>
                        <p className="leading-relaxed mb-2">
                          Represents your aerodynamic resistance. Road position: ~0.30 m². Lower values mean less air resistance.
                        </p>
                        <div className="text-[10px] text-emerald-300">
                          Default chosen for typical road cycling position
                        </div>
                        {/* Arrow */}
                        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 w-2 h-2 bg-slate-900 rotate-45"></div>
                      </div>
                    )}
                  </div>

                  {/* Crr */}
                  <div 
                    className="relative bg-white rounded-lg border border-slate-200 p-3 text-center cursor-help transition-all hover:border-emerald-400 hover:shadow-md"
                    onMouseEnter={() => setHoveredParam('crr')}
                    onMouseLeave={() => setHoveredParam(null)}
                  >
                    <div className="text-xs font-medium text-slate-500 mb-1">Crr</div>
                    <div className="text-lg font-bold text-slate-900">{DEFAULT_CRR}</div>
                    <div className="text-[10px] text-slate-500 mt-1">Rolling resistance</div>
                    
                    {/* Tooltip */}
                    {hoveredParam === 'crr' && (
                      <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-900 text-white text-xs rounded-lg shadow-xl">
                        <div className="font-semibold mb-1">Rolling Resistance Coefficient</div>
                        <p className="leading-relaxed mb-2">
                          Energy lost to tire deformation. Modern 28mm tires at optimal pressure: ~0.004. Lower is better.
                        </p>
                        <div className="text-[10px] text-emerald-300">
                          Default based on quality road tires (28mm)
                        </div>
                        {/* Arrow */}
                        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 w-2 h-2 bg-slate-900 rotate-45"></div>
                      </div>
                    )}
                  </div>

                  {/* Efficiency */}
                  <div 
                    className="relative bg-white rounded-lg border border-slate-200 p-3 text-center cursor-help transition-all hover:border-emerald-400 hover:shadow-md"
                    onMouseEnter={() => setHoveredParam('efficiency')}
                    onMouseLeave={() => setHoveredParam(null)}
                  >
                    <div className="text-xs font-medium text-slate-500 mb-1">Efficiency</div>
                    <div className="text-lg font-bold text-slate-900">
                      {(DEFAULT_CRANK_EFF * 100).toFixed(0)}%
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">Drivetrain</div>
                    
                    {/* Tooltip */}
                    {hoveredParam === 'efficiency' && (
                      <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-900 text-white text-xs rounded-lg shadow-xl">
                        <div className="font-semibold mb-1">Drivetrain Efficiency</div>
                        <p className="leading-relaxed mb-2">
                          Power lost through chain friction. Clean, well-maintained drivetrains: 96-98%. Accounts for ~2-4% loss.
                        </p>
                        <div className="text-[10px] text-emerald-300">
                          Default represents clean, modern drivetrain
                        </div>
                        {/* Arrow */}
                        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 w-2 h-2 bg-slate-900 rotate-45"></div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Card Footer */}
          <div className="bg-slate-50 px-6 py-4 border-t border-slate-200">
            <button
              onClick={handleSave}
              disabled={loading || saveBusy}
              className="w-full rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-6 py-3.5 text-sm font-bold text-white shadow-lg hover:shadow-xl hover:from-emerald-600 hover:to-emerald-700 hover:scale-[1.01] transition-all duration-200 disabled:from-slate-400 disabled:to-slate-500 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:shadow-md flex items-center justify-center gap-2"
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

        {/* Help Text Footer */}
        <div className="mt-6 text-center">
          <p className="text-sm text-slate-500">
            Need help? Check our{" "}
            <a href="#" className="text-emerald-600 hover:text-emerald-700 font-medium">
              documentation
            </a>{" "}
            or{" "}
            <a href="#" className="text-emerald-600 hover:text-emerald-700 font-medium">
              contact support
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
