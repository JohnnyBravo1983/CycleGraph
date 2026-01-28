import { create } from "zustand";
import type { SessionListItem, SessionReport } from "../types/session";
import {
  fetchSessionsList,
  fetchSession as apiFetchSession,
  type FetchSessionResult,
} from "../lib/api";

type LoadSessionOpts = {
  forceRecompute?: boolean;
  profileOverride?: Record<string, any>;
};

interface SessionState {
  sessionsList: SessionListItem[] | null;
  loadingList: boolean;
  errorList: string | null;
  loadSessionsList: () => Promise<void>;

  currentSession: SessionReport | null;
  loadingSession: boolean;
  errorSession: string | null;

  loadSession: (id: string, opts?: LoadSessionOpts) => Promise<void>;
  clearCurrentSession: () => void;

  session: SessionReport | null;
  loading: boolean;
  error: string | null;

  fetchSession: (id: string, opts?: LoadSessionOpts) => Promise<void>;
}

function isRateLimitedFromThrown(err: any): boolean {
  const status = err?.status;
  const detail = err?.detail;
  if (status === 429) {
    const d = detail ?? {};
    const e = d?.error;
    const r = d?.reason;
    if (e === "strava_rate_limited" || r === "read_daily_limit_exceeded") return true;

    // fallback string check
    const s = JSON.stringify(d).toLowerCase();
    if (s.includes("strava_rate_limited") || s.includes("read_daily_limit_exceeded")) return true;
  }

  // extra fallback: sometimes status is nested or string contains 429
  const s = String(err?.message ?? err ?? "").toLowerCase();
  return s.includes("429") && (s.includes("rate") || s.includes("strava"));
}

function isRateLimitedFromResult(result: any): boolean {
  // 1) status/detail shape (if present)
  const status = result?.status;
  const detail = result?.detail;
  if (
    status === 429 &&
    (detail?.error === "strava_rate_limited" ||
      detail?.reason === "read_daily_limit_exceeded")
  ) {
    return true;
  }

  // 2) FetchSessionResult typical: ok:false + error string
  const errStr = String(result?.error ?? "").toLowerCase();
  return (
    errStr.includes("strava_rate_limited") ||
    errStr.includes("read_daily_limit_exceeded") ||
    errStr.includes("rate_limited") ||
    errStr.includes("429")
  );
}

export const useSessionStore = create<SessionState>((set, get) => {
  const runLoadSession = async (id: string, opts?: LoadSessionOpts): Promise<void> => {
    console.log("[sessionStore.loadSession] KALT med id:", id, "opts:", opts);

    set({
      loadingSession: true,
      loading: true,
      errorSession: null,
      error: null,
    });

    let result: FetchSessionResult;

    try {
      result = await (apiFetchSession as any)(id, opts);
    } catch (err: any) {
      // ✅ HOTFIX: Strava 429 er forventet – ikke sett fatal error i store.
      if (isRateLimitedFromThrown(err)) {
        console.warn("[sessionStore.loadSession] rate-limited (thrown):", err?.detail ?? err);
        set({
          loadingSession: false,
          loading: false,
          // IKKE sett errorSession/error her
        });
        return;
      }

      console.error("[sessionStore.loadSession] Uventet feil:", err);
      const msg = "Klarte ikke å hente analyse for økten.";
      set({
        loadingSession: false,
        loading: false,
        currentSession: null,
        session: null,
        errorSession: msg,
        error: msg,
      });
      return;
    }

    if (!result.ok) {
      console.warn(
        "[sessionStore.loadSession] analyze-feil:",
        (result as any)?.error,
        "source=",
        (result as any)?.source
      );

      // ✅ HOTFIX: Ikke trigge errorSession ved Strava rate limit
      if (isRateLimitedFromResult(result)) {
        set({
          loadingSession: false,
          loading: false,
          // IKKE sett errorSession/error her
        });
        return;
      }

      const msg = (result as any)?.error || "Noe gikk galt ved henting av økt.";
      set({
        loadingSession: false,
        loading: false,
        currentSession: null,
        session: null,
        errorSession: msg,
        error: msg,
      });
      return;
    }

    console.log(
      "[sessionStore.loadSession] OK – har session-data (source=",
      result.source,
      ")"
    );

    set((state) => {
      const data: any = result.data as any;

      const patch: any = {};
      if (typeof data.precision_watt_avg === "number")
        patch.precision_watt_avg = data.precision_watt_avg;
      if (typeof data.start_time === "string" || data.start_time === null)
        patch.start_time = data.start_time;
      if (typeof data.distance_km === "number" || data.distance_km === null)
        patch.distance_km = data.distance_km;
      if (typeof data.weather_source === "string" || data.weather_source === null)
        patch.weather_source = data.weather_source;
      if (typeof data.profile_label === "string" || data.profile_label === null)
        patch.profile_label = data.profile_label;
      if (typeof data.debug_source_path === "string" || data.debug_source_path === null)
        patch.debug_source_path = data.debug_source_path;

      const prev = state.sessionsList ?? null;
      let nextList = prev;

      if (Array.isArray(prev)) {
        const target = String(id);
        let hit = false;

        nextList = prev.map((it: any) => {
          const sid = String(it?.session_id ?? "");
          const rid = String(it?.ride_id ?? "");
          if (sid === target || rid === target) {
            hit = true;
            return { ...it, ...patch };
          }
          return it;
        });

        if (hit) {
          console.log("[sessionStore.loadSession] patched sessionsList row", {
            id: target,
            precision_watt_avg: patch.precision_watt_avg,
          });
        } else {
          console.log("[sessionStore.loadSession] no matching row in sessionsList", {
            id: target,
          });
        }
      }

      return {
        loadingSession: false,
        loading: false,
        errorSession: null,
        error: null,
        currentSession: result.data,
        session: result.data,
        sessionsList: nextList,
      };
    });
  };

  return {
    sessionsList: null,
    loadingList: false,
    errorList: null,

    currentSession: null,
    loadingSession: false,
    errorSession: null,

    session: null,
    loading: false,
    error: null,

    loadSessionsList: async (): Promise<void> => {
      if (get().loadingList) {
        console.log("[sessionStore.loadSessionsList] SKIP (already loading)");
        return;
      }

      console.log("[sessionStore.loadSessionsList] KALT");
      set({ loadingList: true, errorList: null });

      try {
        const sessions = await fetchSessionsList();
        console.log(
          "[sessionStore.loadSessionsList] Ferdig – antall sessions:",
          sessions.length
        );
        set({
          sessionsList: sessions,
          loadingList: false,
          errorList: null,
        });
      } catch (err) {
        console.error("[sessionStore.loadSessionsList] Feil:", err);
        set({
          loadingList: false,
          errorList: "Klarte ikke å laste økter fra backend.",
        });
      }
    },

    clearCurrentSession: (): void => {
      set({
        currentSession: null,
        session: null,
        errorSession: null,
        error: null,
        loadingSession: false,
        loading: false,
      });
    },

    loadSession: async (id: string, opts?: LoadSessionOpts): Promise<void> => {
      await runLoadSession(id, opts);
    },

    fetchSession: async (id: string, opts?: LoadSessionOpts): Promise<void> => {
      await runLoadSession(id, opts);
    },
  };
});
