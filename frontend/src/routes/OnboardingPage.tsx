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
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) return v;
  return "";
}

// ✅ PATCH 4D.3 — light theme components
function Tooltip({ text }: { text: string }) {
  return (
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

  // Advanced toggle (keep onboarding non-intimidating)
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    init();
  }, [init]);

  // Auto-check Strava status on mount + URL-change (OAuth redirect)
  useEffect(() => {
    (async () => {
      setStBusy(true);
      setStErr(null);
      try {
        const s = await cgApi.stravaStatus(); // ✅ SSOT for "connected"
        setSt(s);
      } catch (e: unknown) {
        setSt(null);
        setStErr(getErrMsg(e));
      } finally {
        setStBusy(false);
      }
    })();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search]);

  // ---------- draft + key mapping ----------
  const d = useMemo(() => (isObj(draft) ? (draft as AnyRec) : ({} as AnyRec)), [draft]);

  const K = useMemo(() => {
    return {
      // Rider
      weight: resolveKey(d, "rider_weight_kg", ["weight_kg", "weightKg", "weight"]),

      // Bike
      tireWidth: resolveKey(d, "tire_width_mm", ["tireWidthMm", "tire_width", "tireWidth"]),
      bikeWeight: resolveKey(d, "bike_weight_kg", ["bikeWeightKg", "bikeWeight"]),

      // Aero
      cda: resolveKey(d, "cda", ["CdA", "aero_cda", "aeroCdA"]),

      // Advanced
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

  // ✅ Smart defaults (first-time only): only fill missing values once
  const defaultsAppliedRef = useRef(false);
  useEffect(() => {
    if (defaultsAppliedRef.current) return;
    if (!isObj(draft)) return; // wait until draft exists

    const next = { ...(draft as AnyRec) };

    const has = (k: string) => {
      const v = next[k];
      return v !== null && v !== undefined && !(typeof v === "string" && v.trim() === "");
    };

    let changed = false;

    if (!has(K.cda)) {
      next[K.cda] = 0.3;
      changed = true;
    }
    if (!has(K.crr)) {
      next[K.crr] = 0.004;
      changed = true;
    }
    if (!has(K.crankEff)) {
      next[K.crankEff] = 0.96;
      changed = true;
    }
    if (!has(K.tireWidth)) {
      next[K.tireWidth] = 28;
      changed = true;
    }
    // ✅ NEW: bike weight default (reasonable baseline)
    if (!has(K.bikeWeight)) {
      next[K.bikeWeight] = 8.0;
      changed = true;
    }

    if (changed) setDraft(next);
    defaultsAppliedRef.current = true;
  }, [draft, setDraft, K.cda, K.crr, K.crankEff, K.tireWidth, K.bikeWeight]);

  // ✅ PATCH 1B: After “Finish” → re-analyze ALL rides from listAll() + refresh list before navigation
  const onFinish = async () => {
    if (finishBusy) return;
    setFinishBusy(true);

    try {
      console.log("[Onboarding] COMMIT payload", draft);

      // ✅ PATCH: DO NOT write onboarded into the profile
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

        // sort by start_time desc (missing start_time -> last)
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

        // pick ALL IDs
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

        // ✅ PATCH 3: stop bulk re-analyze if Strava rate limited/locked
        for (const sid of pickAll) {
          console.log("[Onboarding] re-analyze sid", sid);
          try {
            await loadSession(String(sid), {
              forceRecompute: true,
              profileOverride: override,
            });
          } catch (e: unknown) {
            // If backend says rate limited -> STOP the loop immediately
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

        // Refresh rides list before navigation
        try {
          await useSessionStore.getState().loadSessionsList();
          console.log("[Onboarding] loadSessionsList refreshed before navigation");
        } catch (e) {
          console.log("[Onboarding] loadSessionsList refresh failed (ignored):", e);
        }
      } catch (e) {
        console.log("[Onboarding] bulk re-analyze error (ignored):", e);
      }

      // ✅ PATCH: hard reload to re-mount AuthGateProvider and get updated onboarding state
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

  // ✅ PATCH 4D.3 — light wrapper + slate header text
  return (
    <div className="max-w-xl mx-auto flex flex-col gap-4 p-4">
      <h1 className="text-2xl font-semibold tracking-tight">Welcome to CycleGraph</h1>

      <p className="text-slate-600">
        Before we begin, we need a rough baseline for your profile. You can adjust this later.
      </p>

      {error ? <div className="text-red-600 text-sm">{error}</div> : null}

      {/* Profile baseline form (aligned with /profile) */}
      <SectionCard title="Rider Info" subtitle="Weight is the most important input.">
        <FieldRow label="Weight (kg)" required>
          <input
            className={inputBase}
            inputMode="decimal"
            placeholder="e.g. 78"
            value={numOrEmpty(d[K.weight])}
            onChange={(e) => update(K.weight, e.target.value === "" ? null : Number(e.target.value))}
          />
          <div className="text-[11px] text-slate-500">Required for accurate FTP modeling.</div>
        </FieldRow>

        {/* ✅ Removed Gender/Age and Country/City */}
      </SectionCard>

      <SectionCard title="Bike Setup" subtitle="Used to estimate rolling losses and speed.">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <FieldRow label="Tire width">
            <select
              className={inputBase}
              value={String(d[K.tireWidth] ?? 28)}
              onChange={(e) => update(K.tireWidth, Number(e.target.value))}
            >
              <option value="25">25mm</option>
              <option value="28">28mm</option>
              <option value="31">30–32mm</option>
            </select>
          </FieldRow>

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
        </div>
      </SectionCard>

      <SectionCard title="Aerodynamics" subtitle="Used to estimate aerodynamic drag.">
        <FieldRow
          label="CdA"
          right={
            <Tooltip text="Aerodynamic drag coefficient (0.250–0.350, lower = faster). Affects FTP modeling." />
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
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <button type="button" onClick={() => setShowAdvanced((s) => !s)} className="w-full text-left">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-900">Advanced settings</div>
              <div className="mt-1 text-xs text-slate-600">
                Optional — you can leave these as defaults.
              </div>
            </div>
            <div className="text-xs text-slate-600">{showAdvanced ? "Hide" : "Show"}</div>
          </div>
        </button>

        {showAdvanced ? (
          <div className="mt-4 flex flex-col gap-3">
            <FieldRow
              label="Crr"
              right={
                <Tooltip text="Rolling resistance (0.0030–0.0050, lower = faster). Affects FTP modeling." />
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
              right={<Tooltip text="Power transfer efficiency (typically 96%). Affects FTP modeling." />}
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

      {/* Strava Connect section */}
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold text-slate-900">Connect Strava</h2>
            <p className="text-sm text-slate-600 mt-1">
              To import rides and build your first analysis, we need access to Strava.
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Backend: <span className="font-mono">{cgApi.baseUrl()}</span>
            </p>
          </div>

          <div className="shrink-0">
            {tokenValid ? (
              <div className="px-3 py-2 rounded-md border border-slate-200 text-sm text-slate-700 bg-slate-50">
                Strava connected ✅
              </div>
            ) : (
              <button
                type="button"
                onClick={connectStrava}
                disabled={stBusy}
                className="px-3 py-2 rounded-md bg-slate-900 text-white text-sm hover:bg-slate-800 disabled:bg-slate-400"
                title={tokenExpired ? "Token expired — connect again" : "Connect Strava"}
              >
                {stBusy ? "Checking…" : tokenExpired ? "Reconnect Strava" : "Connect Strava"}
              </button>
            )}
          </div>
        </div>

        <div className="mt-3 text-sm">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-700">
            <div>
              has_tokens: <span className="font-semibold">{String(st?.has_tokens ?? "unknown")}</span>
            </div>
            <div>
              expires_in_sec:{" "}
              <span className="font-semibold">{String(st?.expires_in_sec ?? "n/a")}</span>
            </div>
            <div>
              uid: <span className="font-mono text-xs">{String(st?.uid ?? "n/a")}</span>
            </div>
          </div>

          {tokenExpired ? (
            <div className="mt-2 text-xs text-amber-700">
              Your Strava token has expired. Click <b>Reconnect Strava</b>, or import a ride later
              from the Dashboard to trigger a refresh.
            </div>
          ) : null}

          {!hasTokens && st ? (
            <div className="mt-2 text-xs text-slate-600">
              You haven’t connected Strava yet. Click{" "}
              <span className="font-semibold">Connect Strava</span> and complete the login — the
              status will update automatically when you return.
            </div>
          ) : null}

          {stErr ? <div className="mt-2 text-xs text-red-600 whitespace-pre-wrap">{stErr}</div> : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 pt-2">
        <button
          type="button"
          onClick={applyDefaults}
          disabled={loading}
          className="px-4 py-2 rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:bg-slate-100"
        >
          Use default values
        </button>

        <button
          type="button"
          onClick={onFinish}
          disabled={loading || finishBusy}
          className="px-4 py-2 rounded-md bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400"
        >
          {finishBusy ? "Finishing…" : "Finish and continue"}
        </button>
      </div>
    </div>
  );
}
