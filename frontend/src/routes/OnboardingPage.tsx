// frontend/src/routes/OnboardingPage.tsx
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useProfileStore } from "../state/profileStore";
import { useSessionStore } from "../state/sessionStore";
import ProfileForm from "../components/ProfileForm";
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

// ---------- helpers (eslint-safe, no any) ----------
function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function getNum(obj: unknown, key: string): number | null {
  if (!isRecord(obj)) return null;
  const v = obj[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function getStr(obj: unknown, key: string): string | null {
  if (!isRecord(obj)) return null;
  const v = obj[key];
  return typeof v === "string" ? v : null;
}

// ✅ Velg nyeste session = max(start_time), ellers fallback til høyeste ride_id
function pickNewestSessionId(items: unknown[]): string | null {
  let bestByTime: { sid: string; t: number } | null = null;
  let bestByNumericId: { sid: string; n: number } | null = null;

  for (const it of items) {
    if (!isRecord(it)) continue;

    const sidRaw = (it as any).session_id ?? (it as any).ride_id;
    const sid = typeof sidRaw === "string" || typeof sidRaw === "number" ? String(sidRaw) : "";
    if (!sid) continue;

    const st = getStr(it, "start_time");
    if (st && st.trim()) {
      const ms = Date.parse(st);
      if (!Number.isNaN(ms)) {
        if (!bestByTime || ms > bestByTime.t) bestByTime = { sid, t: ms };
      }
    }

    const idRaw = (it as any).ride_id ?? (it as any).session_id;
    const idStr =
      typeof idRaw === "string" || typeof idRaw === "number" ? String(idRaw).trim() : "";
    if (idStr) {
      const digits = idStr.replace(/[^\d]/g, "");
      if (digits) {
        const n = Number(digits);
        if (Number.isFinite(n)) {
          if (!bestByNumericId || n > bestByNumericId.n) bestByNumericId = { sid, n };
        }
      }
    }
  }

  return bestByTime?.sid ?? bestByNumericId?.sid ?? null;
}

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

  useEffect(() => {
    init();
  }, [init]);

  // Auto-check status ved mount + URL-change (OAuth redirect)
    // Auto-check Strava status ved mount + URL-change (OAuth redirect)
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


  // ✅ PATCH 1B: Etter “Fullfør” → re-analyze ALLE økter fra listAll() + refresh list før navigation
  const onFinish = async () => {
    if (finishBusy) return;
    setFinishBusy(true);

    try {
      console.log("[Onboarding] COMMIT payload", draft);

      // ✅ PATCH: IKKE skriv onboarded inn i profilen
      const ok = await commit({ markOnboarded: true });
      if (!ok) return;

      // Bygg override (kun tall, no-any)
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

        // sorter på start_time desc (mangler start_time -> sist)
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

        // plukk ALLE IDs
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
          await loadSession(String(sid), {
            forceRecompute: true,
            profileOverride: override,
          });
        }

        // Refresh rides-listen før navigation
        try {
          await useSessionStore.getState().loadSessionsList();
          console.log("[Onboarding] loadSessionsList refreshed before navigation");
        } catch (e) {
          console.log("[Onboarding] loadSessionsList refresh failed (ignored):", e);
        }
      } catch (e) {
        console.log("[Onboarding] bulk re-analyze error (ignored):", e);
      }

      // ✅ PATCH: hard reload for å re-mounte AuthGateProvider og få oppdatert onboarding-state
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
    <div className="max-w-xl mx-auto flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Velkommen til CycleGraph</h1>

      <p className="text-slate-600">
        Før vi starter trenger vi et grovt utgangspunkt for profilen din. Dette kan justeres
        senere.
      </p>

      {error ? <div className="text-red-600 text-sm">{error}</div> : null}

      <ProfileForm value={draft} onChange={setDraft} disabled={loading} />

      {/* Strava Connect section */}
      <div className="rounded-lg border bg-white p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">Koble til Strava</h2>
            <p className="text-sm text-slate-600 mt-1">
              For å hente turer og bygge din første analyse trenger vi tilgang til Strava.
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Backend: <span className="font-mono">{cgApi.baseUrl()}</span>
            </p>
          </div>

          <div className="shrink-0">
            {tokenValid ? (
              <div className="px-3 py-2 rounded border text-sm text-slate-700 bg-slate-50">
                Strava er tilkoblet ✅
              </div>
            ) : (
              <button
                type="button"
                onClick={connectStrava}
                disabled={stBusy}
                className="px-3 py-2 rounded bg-slate-900 text-white text-sm hover:bg-slate-800 disabled:bg-slate-400"
                title={tokenExpired ? "Token er utløpt – koble til på nytt" : "Koble til Strava"}
              >
                {stBusy ? "Sjekker…" : tokenExpired ? "Reconnect Strava" : "Connect Strava"}
              </button>
            )}
          </div>
        </div>

        <div className="mt-3 text-sm">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-700">
            <div>
              has_tokens:{" "}
              <span className="font-semibold">{String(st?.has_tokens ?? "unknown")}</span>
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
              Strava-token er utløpt. Trykk <b>Reconnect Strava</b> eller importer en tur senere i
              Dashboard for å trigge refresh.
            </div>
          ) : null}

          {!hasTokens && st ? (
            <div className="mt-2 text-xs text-slate-600">
              Du har ikke koblet til Strava ennå. Trykk{" "}
              <span className="font-semibold">Connect Strava</span> og fullfør innlogging – så
              oppdateres status automatisk når du kommer tilbake.
            </div>
          ) : null}

          {stErr ? (
            <div className="mt-2 text-xs text-red-600 whitespace-pre-wrap">{stErr}</div>
          ) : null}
        </div>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={applyDefaults}
          disabled={loading}
          className="px-4 py-2 rounded border"
        >
          Bruk standardverdier
        </button>

        <button
          type="button"
          onClick={onFinish}
          disabled={loading || finishBusy}
          className="px-4 py-2 rounded bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-400"
        >
          {finishBusy ? "Fullfører…" : "Fullfør og gå videre"}
        </button>
      </div>
    </div>
  );
}
