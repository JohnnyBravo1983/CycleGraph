/// <reference types="vite/client" />

import { create } from "zustand";
import type { SessionReport } from "../types/session";
import {
  fetchSession as fetchSessionApi,
  fetchSessionsList,
} from "../lib/api";
import type { SessionSummary } from "../lib/api";

type Source = "api" | "mock" | null;

type SessionState = {
  // Enkelt-økt (SessionView)
  session: SessionReport | null;
  loading: boolean;
  error: string | null;
  source: Source;
  fetchSession: (id?: string) => Promise<void>;

  // Øktliste (SessionsPage / Rides)
  sessionsList: SessionSummary[] | null;
  loadingList: boolean;
  errorList: string | null;
  loadSessionsList: () => Promise<void>;
};

function getMode(): "api" | "mock" {
  const env = (import.meta as unknown as { env?: Record<string, string | undefined> }).env;
  const raw = env?.VITE_BACKEND_MODE as "api" | "mock" | undefined;
  return raw === "api" ? "api" : "mock";
}

export const useSessionStore = create<SessionState>((set) => ({
  // Enkelt-økt (SessionView)
  session: null,
  loading: false,
  error: null,
  source: null,

  // Øktliste (SessionsPage / Rides)
  sessionsList: null,
  loadingList: false,
  errorList: null,

  async fetchSession(id?: string) {
    set({ loading: true, error: null });

    const mode = getMode();
    const effectiveId = mode === "api" ? (id ?? "mock") : "mock";

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

  async loadSessionsList() {
    set({ loadingList: true, errorList: null });

    try {
      // fetchSessionsList() returnerer nå rett SessionSummary[]
      const list = await fetchSessionsList();

      set({
        sessionsList: list,
        loadingList: false,
        errorList: null,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      set({
        sessionsList: null,
        loadingList: false,
        errorList: msg,
      });
    }
  },
}));
