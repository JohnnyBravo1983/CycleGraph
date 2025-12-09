// frontend/src/state/sessionStore.ts
import { create } from "zustand";
import type { SessionListItem, SessionReport } from "../types/session";
import {
  fetchSessionsList,
  fetchSession as apiFetchSession,
  type FetchSessionResult,
} from "../lib/api";

interface SessionState {
  // 🔹 Listevisning (/api/sessions/list)
  sessionsList: SessionListItem[] | null;
  loadingList: boolean;
  errorList: string | null;
  loadSessionsList: () => Promise<void>;

  // 🔹 Detaljvisning (SessionView – analyze for én økt)
  session: SessionReport | null;
  loading: boolean;
  error: string | null;
  fetchSession: (id: string) => Promise<void>;
}

export const useSessionStore = create<SessionState>((set) => ({
  // 🚩 Init state – liste
  sessionsList: null,
  loadingList: false,
  errorList: null,

  // 🚩 Init state – enkelt-session
  session: null,
  loading: false,
  error: null,

  // -----------------------------
  // Liste: /api/sessions/list
  // -----------------------------
  async loadSessionsList() {
    console.log("[sessionStore.loadSessionsList] KALT");
    set({ loadingList: true, errorList: null });
    try {
      const sessions = await fetchSessionsList();
      console.log(
        "[sessionStore.loadSessionsList] Ferdig – antall sessions:",
        sessions.length,
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

  // -----------------------------
  // Enkelt-økt: POST /api/sessions/{sid}/analyze
  // -----------------------------
  async fetchSession(id: string) {
    console.log("[sessionStore.fetchSession] KALT med id:", id);
    set({ loading: true, error: null });

    let result: FetchSessionResult;
    try {
      result = await apiFetchSession(id);
    } catch (err) {
      console.error("[sessionStore.fetchSession] Uventet feil:", err);
      set({
        loading: false,
        error: "Klarte ikke å hente analyse for økten.",
      });
      return;
    }

    if (!result.ok) {
      console.warn(
        "[sessionStore.fetchSession] analyze-feil:",
        result.error,
        "source=",
        result.source,
      );
      set({
        loading: false,
        error: result.error || "Noe gikk galt ved henting av økt.",
      });
      return;
    }

    console.log("[sessionStore.fetchSession] OK – har session-data");
    set({
      session: result.data,
      loading: false,
      error: null,
    });
  },
}));
