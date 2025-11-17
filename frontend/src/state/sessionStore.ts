/// <reference types="vite/client" />

import { create } from "zustand";
import type { SessionReport, SessionInfo } from "../types/session";
import {
  fetchSession as fetchSessionApi,
  analyze as analyzeApi,
  getSessionsList as getSessionsListApi,
} from "../lib/api";
import type { AnalyzeResponse, Profile } from "../lib/schema";

type Source = "api" | "mock" | null;

type SessionState = {
  session: SessionReport | null;
  loading: boolean;
  error: string | null;
  source: Source;

  // --- Trinn 2: analyze-resultater ---
  analyzeResult: AnalyzeResponse | null;
  analyzeLoading: boolean;
  analyzeError: string | null;

  // --- Trinn 6: sessions-liste ---
  sessions: SessionInfo[] | null;
  sessionsLoading: boolean;
  sessionsError: string | null;

  fetchSession: (id?: string) => Promise<void>;
  analyzeSession: (id: string) => Promise<void>;

  // --- Ny: sessions-liste ---
  fetchSessionsList: () => Promise<void>;

  // --- Trinn 4: profil-lagring + re-analyze ---
  saveProfileAndReanalyze: (sessionId: string, profile: Profile) => Promise<void>;
};

function getMode(): "api" | "mock" {
  const env = (import.meta as unknown as { env?: Record<string, string | undefined> }).env;
  const raw = env?.VITE_BACKEND_MODE as "api" | "mock" | undefined;
  return raw === "api" ? "api" : "mock";
}

export const useSessionStore = create<SessionState>((set) => ({
  session: null,
  loading: false,
  error: null,
  source: null,

  // --- Trinn 2: analyze-session state ---
  analyzeResult: null,
  analyzeLoading: false,
  analyzeError: null,

  // --- Trinn 6: sessions-liste ---
  sessions: null,
  sessionsLoading: false,
  sessionsError: null,

  async fetchSession(id?: string) {
    set({ loading: true, error: null });

    const mode = getMode();
    const effectiveId = mode === "api" ? (id ?? "mock") : "mock";

    // Nytt:
    // I API-modus for ekte økter (ikke mock), hopper vi over legacy-endepunktet
    // /api/analyze_session og lar analyzeResult være den "sanne" kilden.
    if (
      mode === "api" &&
      id &&
      id !== "mock" &&
      id !== "mock-short" &&
      id !== "mock-2h"
    ) {
      set({
        session: null,
        loading: false,
        error: null,
        source: "api",
      });
      return;
    }

    try {
      const res = await fetchSessionApi(effectiveId);

      if (res.ok) {
        set({
          session: res.data,
          loading: false,
          error: null,
          source: res.source === "live" ? "api" : "mock",
        });
      } else {
        set({
          session: null,
          loading: false,
          error: res.error,
          source: res.source === "live" ? "api" : res.source ?? mode,
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      set({
        session: null,
        loading: false,
        error: msg,
        source: mode,
      });
    }
  },

  async analyzeSession(id: string) {
    set({ analyzeLoading: true, analyzeError: null });

    try {
      // Kall backend direkte via api.analyze
      const res = await analyzeApi(id);

      console.log("[SESSION STORE] analyzeSession result", { id, res });

      if (!res) {
        set({
          analyzeResult: null,
          analyzeLoading: false,
          analyzeError: "Analyse ble avbrutt eller ga ingen data.",
        });
        return;
      }

      set({
        analyzeResult: res,
        analyzeLoading: false,
        analyzeError: null,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      set({
        analyzeResult: null,
        analyzeLoading: false,
        analyzeError: msg,
      });
    }
  },

  async fetchSessionsList() {
    set({ sessionsLoading: true, sessionsError: null });

    try {
      const list = await getSessionsListApi();

      set({
        sessions: list,
        sessionsLoading: false,
        sessionsError: null,
      });
    } catch (err: unknown) {
      console.error("[SESSION STORE] fetchSessionsList error", err);
      set({
        sessions: null,
        sessionsLoading: false,
        sessionsError:
          err instanceof Error ? err.message : "Kunne ikke hente økter",
      });
    }
  },

  async saveProfileAndReanalyze(sessionId: string, profile: Profile) {
    set({ analyzeLoading: true, analyzeError: null });

    try {
      // Samme mønster som analyzeSession – bruk dynamisk import for setProfile
      const api = await import("../lib/api");

      // 1) Lagre profil (backend øker profile_version og returnerer oppdatert Profile)
      await api.setProfile(profile);

      // 2) Kjør analyze på aktuelt sessionId
      const res = await analyzeApi(sessionId);

      if (!res) {
        set({
          analyzeResult: null,
          analyzeLoading: false,
          analyzeError: "Analyse avbrutt",
        });
        return;
      }

      set({
        analyzeResult: res,
        analyzeLoading: false,
        analyzeError: null,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      set({
        analyzeResult: null,
        analyzeLoading: false,
        analyzeError: msg,
      });
    }
  },
}));
