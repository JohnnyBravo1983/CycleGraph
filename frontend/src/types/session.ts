// frontend/src/state/sessionStore.ts
import { create } from "zustand";
import type { SessionListItem, SessionReport } from "../types/session";
import { fetchSessionsList, fetchSession } from "../lib/api";

type SessionStore = {
  // List
  sessionsList: SessionListItem[] | null;
  loadingList: boolean;
  errorList: string | null;

  // Single session (SessionView)
  currentSession: SessionReport | null;
  loadingSession: boolean;
  errorSession: string | null;

  // Actions
  loadSessionsList: () => Promise<void>;
  loadSession: (id: string) => Promise<void>;
  clearCurrentSession: () => void;
};

function normalizeId(id: unknown): string {
  if (id === null || id === undefined) return "";
  return String(id);
}

/**
 * Backend har historisk levert litt ulike felt:
 * - `session_id` (vår foretrukne)
 * - `id` (noen ganger samme som ride_id)
 * - `ride_id`
 *
 * Vi normaliserer til SessionListItem med `session_id` + `ride_id`.
 */
function mapListRow(raw: any): SessionListItem | null {
  const session_id =
    normalizeId(raw?.session_id) || normalizeId(raw?.id) || normalizeId(raw?.ride_id);

  const ride_id = normalizeId(raw?.ride_id) || normalizeId(raw?.id) || session_id;

  if (!session_id || !ride_id) return null;

  return {
    session_id,
    ride_id,
    start_time: raw?.start_time ?? null,
    distance_km: raw?.distance_km ?? null,
    precision_watt_avg: raw?.precision_watt_avg ?? null,
    profile_label:
      raw?.profile_label ??
      raw?.profile_used ??
      raw?.profile ??
      raw?.profile_version ??
      null,
    weather_source: raw?.weather_source ?? raw?.weather?.source ?? null,
  };
}

export const useSessionStore = create<SessionStore>((set, get) => ({
  // List
  sessionsList: null,
  loadingList: false,
  errorList: null,

  // Single session
  currentSession: null,
  loadingSession: false,
  errorSession: null,

  loadSessionsList: async () => {
    // Unngå dobbeltkall (React StrictMode kan trigge)
    if (get().loadingList) return;

    set({ loadingList: true, errorList: null });

    try {
      const raw = await fetchSessionsList();

      // fetchSessionsList kan returnere enten:
      // - en array direkte
      // - eller en { ok, data }-variant (avhengig av din api.ts)
      const rows: any[] = Array.isArray(raw) ? raw : (raw as any)?.data ?? [];

      const mapped = rows
        .map(mapListRow)
        .filter((x): x is SessionListItem => Boolean(x));

      set({ sessionsList: mapped, loadingList: false, errorList: null });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      set({ sessionsList: [], loadingList: false, errorList: msg });
    }
  },

  loadSession: async (id: string) => {
    if (!id) {
      set({ currentSession: null, errorSession: "Mangler session-id", loadingSession: false });
      return;
    }

    // Unngå dobbeltkall
    if (get().loadingSession) return;

    set({ loadingSession: true, errorSession: null });

    try {
      const result = await fetchSession(id);

      if (!result.ok) {
        set({
          currentSession: null,
          errorSession: result.error || "Noe gikk galt ved henting av økt",
          loadingSession: false,
        });
        return;
      }

      // ✅ PATCH 2 endring: sørg for at error nulles når vi får live data
      console.log("[SessionStore] LIVE session parsed:", result.data);
      set({
        currentSession: result.data,
        errorSession: null,
        loadingSession: false,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      set({
        currentSession: null,
        errorSession: msg,
        loadingSession: false,
      });
    }
  },

  clearCurrentSession: () => {
    set({ currentSession: null, loadingSession: false, errorSession: null });
  },
}));
