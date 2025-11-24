/// <reference types="vite/client" />

import { create } from "zustand";
import type { SessionReport } from "../types/session";
import {
  fetchSession as fetchSessionApi,
  analyze as analyzeApi,
  fetchSessionsList,
} from "../lib/api";
import type { AnalyzeResponse, Profile } from "../lib/schema";
import type { SessionSummary } from "../lib/api";

type Source = "api" | "mock" | null;

type SessionState = {
  // Enkeltsesjon (legacy / session-endepunktet)
  session: SessionReport | null;
  loading: boolean;
  error: string | null;
  source: Source;

  // Analyze-resultater
  analyzeResult: AnalyzeResponse | null;
  analyzeLoading: boolean;
  analyzeError: string | null;

  // Sessions-liste (nå bygget fra trend/summary.csv via SessionSummary)
  sessionsList: SessionSummary[] | null;
  loadingList: boolean;
  errorList: string | null;

  // Actions
  fetchSession: (id?: string) => Promise<void>;
  analyzeSession: (id: string) => Promise<void>;
  loadSessionsList: () => Promise<void>;
  saveProfileAndReanalyze: (sessionId: string, profile: Profile) => Promise<void>;
};

function getMode(): "api" | "mock" {
  const env = (import.meta as unknown as { env?: Record<string, string | undefined> }).env;
  const raw = env?.VITE_BACKEND_MODE as "api" | "mock" | undefined;
  return raw === "api" ? "api" : "mock";
}

export const useSessionStore = create<SessionState>((set) => ({
  // --- State ---
  session: null,
  loading: false,
  error: null,
  source: null,

  analyzeResult: null,
  analyzeLoading: false,
  analyzeError: null,

  sessionsList: null,
  loadingList: false,
  errorList: null,

  // -------------------------------------------------------------------------
  // Hent én økt (legacy / session-endepunktet)
  // -------------------------------------------------------------------------
  async fetchSession(id?: string) {
    set({ loading: true, error: null });

    const mode = getMode();
    const effectiveId = mode === "api" ? (id ?? "mock") : "mock";

    if (
      mode === "api" &&
      id &&
      id !== "mock" &&
      id !== "mock-short" &&
      id !== "mock-2h"
    ) {
      // I API-modus for ekte sessions henter vi ikke legacy-session-data.
      // SessionCard bruker analyzeResult (mapAnalyzeToCard) i stedet.
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

  // -------------------------------------------------------------------------
  // Analyze – kjør backend-analyse for en gitt sessionId
  // -------------------------------------------------------------------------
  async analyzeSession(id: string) {
    set({ analyzeLoading: true, analyzeError: null });

    try {
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

  // -------------------------------------------------------------------------
  // Sessions-liste – brukt i /sessions-route
  // Nå koblet til fetchSessionsList() → summary.csv → SessionSummary[]
  // -------------------------------------------------------------------------
  loadSessionsList: async () => {
    set({ loadingList: true, errorList: null });

    try {
      console.log("[SESSION STORE] loadSessionsList → fetchSessionsList()");
      const sessions = await fetchSessionsList();

      set({
        sessionsList: sessions,
        loadingList: false,
      });
    } catch (err: unknown) {
      console.error("[SESSION STORE] loadSessionsList error", err);
      set({
        errorList:
          err instanceof Error ? err.message : "Kunne ikke hente økter",
        loadingList: false,
      });
    }
  },

  // -------------------------------------------------------------------------
  // Lagre profil til backend og kjør analyze på nytt
  // -------------------------------------------------------------------------
  async saveProfileAndReanalyze(sessionId: string, profile: Profile) {
    set({ analyzeLoading: true, analyzeError: null });

    try {
      const api = await import("../lib/api");

      // 1) Lagre profil (backend oppdaterer profile_version)
      await api.setProfile(profile);

      // 2) Kjør analyze på nytt for denne økten
      const res = await analyzeApi(sessionId);

      console.log("[SESSION STORE] saveProfileAndReanalyze result", {
        sessionId,
        res,
      });

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
