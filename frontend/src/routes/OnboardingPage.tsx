// frontend/src/routes/OnboardingPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useProfileStore } from "../state/profileStore";
import { useSessionStore } from "../state/sessionStore";
import { cgApi, type StatusResp } from "../lib/cgApi";

function getErrMsg(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

type TokenState = "unknown" | "missing" | "expired" | "valid";

function getTokenState(st: StatusResp | null): TokenState {
  if (!st) return "unknown";
  if (st.has_tokens !== true) return "missing";
  const exp = typeof st.expires_in_sec === "number" ? st.expires_in_sec : null;
  if (exp !== null && exp <= 0) return "expired";
  return "valid";
}

// ---------- helpers (eslint-safe) ----------
type AnyRec = Record<string, any>;
function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}
function isObj(v: unknown): v is AnyRec {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
function getNum(obj: unknown, key: string): number | null {
  if (!isRecord(obj)) return null;
  const v = (obj as Record<string, unknown>)[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function resolveKey(draft: AnyRec, preferred: string, fallbacks: string[]): string {
  if (preferred in draft) return preferred;
  for (const k of fallbacks) if (k in draft) return k;
  return preferred;
}
function numOrEmpty(v: unknown): string {
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "string" && v.trim() !== "") return v;
  return "";
}

const inputBase =
  "w-full rounded-lg border-2 border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all duration-200";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const { draft, loading, error, init, setDraft, applyDefaults, commit } = useProfileStore();
  const { loadSession } = useSessionStore();

  // Strava status UI state
  const [st, setSt] = useState<StatusResp | null>(null);
  const [stBusy, setStBusy] = useState(false);
  const [stErr, setStErr] = useState<string | null>(null);

  // prevent double submit
  const [finishBusy, setFinishBusy] = useState(false);

  // Hover state for tooltips
  const [hoveredParam, setHoveredParam] = useState<string | null>(null);

  useEffect(() => {
    init();
  }, [init]);

  // Auto-check Strava status on mount + URL-change (OAuth redirect)
  useEffect(() => {
    (async () => {
      setStBusy(true);
      setStErr(null);
      try {
        const s = await cgApi.stravaStatus();
        setSt(s);
      } catch (e: unknown) {
        setSt(null);
        setStErr(getErrMsg(e));
      } finally {
        setStBusy(false);
      }
    })();
  }, [location.pathname, location.search]);

  // ---------- draft + key mapping ----------
  const d = useMemo(() => (isObj(draft) ? (draft as AnyRec) : ({} as AnyRec)), [draft]);

  const K = useMemo(() => {
    return {
      // Rider
      weight: resolveKey(d, "rider_weight_kg", ["weight_kg", "weightKg", "weight"]),

      // Bike
      bikeWeight: resolveKey(d, "bike_weight_kg", ["bikeWeightKg", "bikeWeight"]),

      // Defaults / model params
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
    setDraft({ ...d, [key]: value });
  }

  // Handle decimal input - allows both integers and decimals
  const handleDecimalInput = (key: string, value: string) => {
    // Allow empty string
    if (value === "") {
      update(key, null);
      return;
    }

    // Allow partial decimal inputs like "75." or "8."
    if (value.endsWith('.') && value.split('.').length === 2) {
      update(key, value);
      return;
    }

    // Validate and convert to number
    const parsed = parseFloat(value);
    if (!isNaN(parsed) && isFinite(parsed)) {
      update(key, parsed);
    }
  };

  // Defaults we want for March launch
  const DEFAULT_CDA = 0.3;
  const DEFAULT_CRR = 0.004;
  const DEFAULT_CRANK_EFF = 0.96;

  // Smart defaults (first-time only): only fill missing values once
  const defaultsAppliedRef = useRef(false);
  useEffect(() => {
    if (defaultsAppliedRef.current) return;
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
    defaultsAppliedRef.current = true;
  }, [draft, setDraft, K.cda, K.crr, K.crankEff, K.bikeWeight]);

  const onFinish = async () => {
    if (finishBusy) return;
    setFinishBusy(true);

    try {
      console.log("[Onboarding] COMMIT payload", draft);

      const ok = await commit({ markOnboarded: true });
      if (!ok) return;

      // Build override (numbers only, no-any)
      const override: Record<string, number> = {};
      const rw = getNum(draft, "rider_weight_kg");
      const bw = getNum(draft, "bike_weight_kg");
      const cda = getNum(draft, "cda");
      const crr = getNum(draft, "crr");
      const ce = getNum(draft, "crank_efficiency");
      const cep = getNum(draft, "crank_eff_pct");

      if (rw !== null) override.rider_weight_kg = rw;
      if (bw !== null) override.bike_weight_kg = bw;
      if (cda !== null) override.cda = cda;
      if (crr !== null) override.crr = crr;
      if (ce !== null) override.crank_efficiency = ce;
      if (cep !== null) override.crank_eff_pct = cep;

      try {
        const itemsUnknown = (await cgApi.listAll().catch(() => [])) as unknown;
        const items: unknown[] = Array.isArray(itemsUnknown) ? itemsUnknown : [];

        const sorted = [...items].sort((a, b) => {
          const sa = isRecord(a)
            ? typeof (a as any).start_time === "string"
              ? (a as any).start_time
              : ""
            : "";
          const sb = isRecord(b)
            ? typeof (b as any).start_time === "string"
              ? (b as any).start_time
              : ""
            : "";
          const ta = Date.parse(sa) || 0;
          const tb = Date.parse(sb) || 0;
          return tb - ta;
        });

        const pickAll = sorted
          .map((x) => {
            if (!isRecord(x)) return "";
            const raw = (x as any).session_id ?? (x as any).ride_id;
            return typeof raw === "string" || typeof raw === "number" ? String(raw) : "";
          })
          .filter((s) => Boolean(s));

        console.log("[Onboarding] bulk re-analyze ALL", {
          count: pickAll.length,
          override,
        });

        for (const sid of pickAll) {
          console.log("[Onboarding] re-analyze sid", sid);
          try {
            await loadSession(String(sid), {
              forceRecompute: true,
              profileOverride: override,
            });
          } catch (e: unknown) {
            const msg = String((e as any)?.message ?? "");
            if (
              msg.includes("429") ||
              msg.includes("STRAVA_RATE_LIMITED") ||
              msg.includes("strava_rate_limited")
            ) {
              console.log("[Onboarding] bulk re-analyze STOP (rate limited):", e);
              break;
            }
            console.log("[Onboarding] bulk re-analyze error (ignored):", e);
          }
        }

        try {
          await useSessionStore.getState().loadSessionsList();
          console.log("[Onboarding] loadSessionsList refreshed before navigation");
        } catch (e) {
          console.log("[Onboarding] loadSessionsList refresh failed (ignored):", e);
        }
      } catch (e) {
        console.log("[Onboarding] bulk re-analyze error (ignored):", e);
      }

      window.location.assign("/onboarding/import");
      return;
    } finally {
      setFinishBusy(false);
    }
  };

  function connectStrava() {
    const nextRaw = `${window.location.origin}/onboarding`;
    const url = `${cgApi.baseUrl()}/api/auth/strava/login?next=${encodeURIComponent(nextRaw)}`;
    window.open(url, "_self");
  }

  const tokenState = getTokenState(st);
  const tokenValid = tokenState === "valid";
  const tokenExpired = tokenState === "expired";
  const hasTokens = st?.has_tokens === true;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Welcome to CycleGraph</h1>
          <p className="text-slate-600">
            Before we begin, we need a rough baseline for your profile. You can adjust this later.
          </p>
        </div>

        {error ? <div className="text-red-600 text-sm mb-4">{error}</div> : null}

        {/* Main Card */}
        <div className="rounded-2xl bg-white shadow-xl border border-slate-200 overflow-hidden mb-6">
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
                pattern="[0-9]*\.?[0-9]*"
                placeholder="e.g. 75.5"
                value={numOrEmpty(d[K.weight])}
                onChange={(e) => handleDecimalInput(K.weight, e.target.value)}
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
                <span>Required for accurate FTP modeling and climbing power calculations.</span>
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
                pattern="[0-9]*\.?[0-9]*"
                placeholder="e.g. 8.2"
                value={numOrEmpty(d[K.bikeWeight])}
                onChange={(e) => handleDecimalInput(K.bikeWeight, e.target.value)}
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
                      We've set sensible defaults based on typical road cycling. Hover over each to
                      see what it means in real terms.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  {/* CdA */}
                  <div
                    className="relative bg-white rounded-lg border-2 border-slate-200 p-3 text-center cursor-help transition-all hover:border-emerald-400 hover:shadow-md"
                    onMouseEnter={() => setHoveredParam('cda')}
                    onMouseLeave={() => setHoveredParam(null)}
                  >
                    <div className="text-xs font-medium text-slate-500 mb-1">CdA</div>
                    <div className="text-lg font-bold text-slate-900">{DEFAULT_CDA}</div>
                    <div className="text-[10px] text-slate-500 mt-1">Air resistance</div>

                    {/* Tooltip */}
                    {hoveredParam === 'cda' && (
                      <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 p-4 bg-slate-900 text-white text-xs rounded-lg shadow-2xl">
                        <div className="font-bold mb-2 text-sm text-emerald-300">
                          Wind Resistance (CdA)
                        </div>
                        <p className="leading-relaxed mb-3">
                          This measures how much the wind slows you down. Think of it like your
                          "size" to the wind.
                        </p>
                        <div className="bg-slate-800 rounded p-2 mb-3">
                          <div className="font-semibold mb-1">Real example:</div>
                          <div className="text-[11px] leading-relaxed">
                            At 35 km/h, improving from 0.30 to 0.27 (aero position) saves you{' '}
                            <span className="text-emerald-300 font-bold">~25 seconds per 40km</span>
                            .
                          </div>
                        </div>
                        <div className="text-[10px] text-slate-300">
                          ✓ We use 0.30 as default (normal road position with hoods)
                        </div>
                        {/* Arrow */}
                        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 w-2 h-2 bg-slate-900 rotate-45"></div>
                      </div>
                    )}
                  </div>

                  {/* Crr */}
                  <div
                    className="relative bg-white rounded-lg border-2 border-slate-200 p-3 text-center cursor-help transition-all hover:border-emerald-400 hover:shadow-md"
                    onMouseEnter={() => setHoveredParam('crr')}
                    onMouseLeave={() => setHoveredParam(null)}
                  >
                    <div className="text-xs font-medium text-slate-500 mb-1">Crr</div>
                    <div className="text-lg font-bold text-slate-900">{DEFAULT_CRR}</div>
                    <div className="text-[10px] text-slate-500 mt-1">Tire resistance</div>

                    {/* Tooltip */}
                    {hoveredParam === 'crr' && (
                      <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 p-4 bg-slate-900 text-white text-xs rounded-lg shadow-2xl">
                        <div className="font-bold mb-2 text-sm text-emerald-300">
                          Rolling Resistance (Crr)
                        </div>
                        <p className="leading-relaxed mb-3">
                          How much energy your tires "waste" by squishing against the road. Lower is
                          faster.
                        </p>
                        <div className="bg-slate-800 rounded p-2 mb-3">
                          <div className="font-semibold mb-1">Real example:</div>
                          <div className="text-[11px] leading-relaxed">
                            Upgrading from cheap tires (0.006) to quality tires (0.004) saves you{' '}
                            <span className="text-emerald-300 font-bold">~1 minute per 40km</span> at
                            30 km/h.
                          </div>
                        </div>
                        <div className="text-[10px] text-slate-300">
                          ✓ We use 0.004 as default (modern 28mm road tires, proper pressure)
                        </div>
                        {/* Arrow */}
                        <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 w-2 h-2 bg-slate-900 rotate-45"></div>
                      </div>
                    )}
                  </div>

                  {/* Efficiency */}
                  <div
                    className="relative bg-white rounded-lg border-2 border-slate-200 p-3 text-center cursor-help transition-all hover:border-emerald-400 hover:shadow-md"
                    onMouseEnter={() => setHoveredParam('efficiency')}
                    onMouseLeave={() => setHoveredParam(null)}
                  >
                    <div className="text-xs font-medium text-slate-500 mb-1">Efficiency</div>
                    <div className="text-lg font-bold text-slate-900">
                      {(DEFAULT_CRANK_EFF * 100).toFixed(0)}%
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">Power loss</div>

                    {/* Tooltip */}
                    {hoveredParam === 'efficiency' && (
                      <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 p-4 bg-slate-900 text-white text-xs rounded-lg shadow-2xl">
                        <div className="font-bold mb-2 text-sm text-emerald-300">
                          Drivetrain Efficiency
                        </div>
                        <p className="leading-relaxed mb-3">
                          How much power is lost in your chain and gears before it reaches the rear
                          wheel.
                        </p>
                        <div className="bg-slate-800 rounded p-2 mb-3">
                          <div className="font-semibold mb-1">Real example:</div>
                          <div className="text-[11px] leading-relaxed">
                            A dirty chain (93% efficiency) vs clean chain (97% efficiency) means you
                            lose <span className="text-emerald-300 font-bold">~8 watts</span> at 200W
                            output. That's ~30 seconds per 40km.
                          </div>
                        </div>
                        <div className="text-[10px] text-slate-300">
                          ✓ We use 96% as default (clean, well-maintained modern drivetrain)
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
        </div>

        {/* Strava Connect Card */}
        <div className="rounded-2xl bg-white shadow-xl border border-slate-200 overflow-hidden mb-6">
          <div className="p-6">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="font-bold text-slate-900 text-lg mb-1">Connect Strava</h2>
                <p className="text-sm text-slate-600">
                  To import rides and build your first analysis, we need access to Strava.
                </p>
              </div>

              <div className="shrink-0">
                {tokenValid ? (
                  <div className="px-4 py-2 rounded-lg border-2 border-emerald-200 text-sm font-semibold text-emerald-700 bg-emerald-50">
                    ✓ Connected
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={connectStrava}
                    disabled={stBusy}
                    className="px-4 py-2 rounded-lg bg-[#FC4C02] text-white text-sm font-bold hover:bg-[#E34402] disabled:bg-slate-400 transition-all shadow-md hover:shadow-lg flex items-center gap-2"
                    title={tokenExpired ? "Token expired — connect again" : "Connect Strava"}
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169" />
                    </svg>
                    {stBusy ? "Checking…" : tokenExpired ? "Reconnect" : "Connect Strava"}
                  </button>
                )}
              </div>
            </div>

            {/* Status details */}
            <div className="mt-4 p-3 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                <div>
                  Status: <span className="font-semibold">{String(st?.has_tokens ?? "unknown")}</span>
                </div>
                <div>
                  Expires:{" "}
                  <span className="font-semibold">{String(st?.expires_in_sec ?? "n/a")}</span>
                </div>
                <div>
                  UID: <span className="font-mono text-[10px]">{String(st?.uid ?? "n/a")}</span>
                </div>
              </div>

              {tokenExpired ? (
                <div className="mt-2 text-xs text-amber-700">
                  Your Strava token has expired. Click <b>Reconnect</b> to refresh.
                </div>
              ) : null}

              {!hasTokens && st ? (
                <div className="mt-2 text-xs text-slate-600">
                  Click <span className="font-semibold">Connect Strava</span> and complete the login
                  — the status will update automatically when you return.
                </div>
              ) : null}

              {stErr ? (
                <div className="mt-2 text-xs text-red-600 whitespace-pre-wrap">{stErr}</div>
              ) : null}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={applyDefaults}
            disabled={loading}
            className="px-6 py-3 rounded-xl border-2 border-slate-200 bg-white text-slate-700 font-semibold hover:bg-slate-50 disabled:bg-slate-100 transition-all"
          >
            Use default values
          </button>

          <button
            type="button"
            onClick={onFinish}
            disabled={loading || finishBusy}
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-bold shadow-lg hover:shadow-xl hover:from-emerald-600 hover:to-emerald-700 hover:scale-[1.01] transition-all duration-200 disabled:from-slate-400 disabled:to-slate-500 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center gap-2"
          >
            {finishBusy ? (
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
                Finishing…
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M13 7l5 5m0 0l-5 5m5-5H6"
                  />
                </svg>
                Finish and continue
              </>
            ))}
          </button>
        </div>
      </div>
    </div>
  );
}
