// frontend/src/state/sessionStore.ts
import { create } from "zustand";
import type { SessionListItem, SessionReport } from "../types/session";
import {
  fetchSessionsList,
  fetchSession as apiFetchSession,
  type FetchSessionResult,
} from "../lib/api";

interface SessionState {
  // ─────────────────────────────────────────────────────────────
  // Listevisning (/api/sessions/list)
  // ─────────────────────────────────────────────────────────────
  sessionsList: SessionListItem[] | null;
  loadingList: boolean;
  errorList: string | null;
  loadSessionsList: () => Promise<void>;

  // ─────────────────────────────────────────────────────────────
  // Enkelt-økt (navn som SessionView forventer)
  // ─────────────────────────────────────────────────────────────
  currentSession: SessionReport | null;
  loadingSession: boolean;
  errorSession: string | null;

  loadSession: (id: string) => Promise<void>;
  clearCurrentSession: () => void;

  // ─────────────────────────────────────────────────────────────
  // Backward compatibility (gamle navn)
  // ─────────────────────────────────────────────────────────────
  session: SessionReport | null;
  loading: boolean;
  error: string | null;

  fetchSession: (id: string) => Promise<void>;
}

export const useSessionStore = create<SessionState>((set) => {
  // ✅ Intern helper: unngår self-reference til useSessionStore i initializer
  const runLoadSession = async (id: string): Promise<void> => {
    console.log("[sessionStore.loadSession] KALT med id:", id);

    set({
      loadingSession: true,
      loading: true, // alias
      errorSession: null,
      error: null, // alias
    });

    let result: FetchSessionResult;
    try {
      result = await apiFetchSession(id);
    } catch (err) {
      console.error("[sessionStore.loadSession] Uventet feil:", err);
      const msg = "Klarte ikke å hente analyse for økten.";
      set({
        loadingSession: false,
        loading: false, // alias
        currentSession: null,
        session: null, // alias
        errorSession: msg,
        error: msg, // alias
      });
      return;
    }

    if (!result.ok) {
      console.warn(
        "[sessionStore.loadSession] analyze-feil:",
        result.error,
        "source=",
        result.source,
      );
      const msg = result.error || "Noe gikk galt ved henting av økt.";
      set({
        loadingSession: false,
        loading: false, // alias
        currentSession: null,
        session: null, // alias
        errorSession: msg,
        error: msg, // alias
      });
      return;
    }

    console.log(
      "[sessionStore.loadSession] OK – har session-data (source=",
      result.source,
      ")",
    );

    set({
      loadingSession: false,
      loading: false, // alias
      errorSession: null,
      error: null, // alias
      currentSession: result.data,
      session: result.data, // alias
    });
  };

  return {
    // 🚩 Init state – liste
    sessionsList: null,
    loadingList: false,
    errorList: null,

    // 🚩 Init state – enkelt-session (nye)
    currentSession: null,
    loadingSession: false,
    errorSession: null,

    // 🚩 Init state – enkelt-session (aliases)
    session: null,
    loading: false,
    error: null,

    // -----------------------------
    // Liste: /api/sessions/list
    // -----------------------------
    loadSessionsList: async (): Promise<void> => {
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
    // Clear (brukes av SessionView)
    // -----------------------------
    clearCurrentSession: (): void => {
      set({
        currentSession: null,
        session: null, // alias
        errorSession: null,
        error: null, // alias
        loadingSession: false,
        loading: false, // alias
      });
    },

    // -----------------------------
    // Ny action (SessionView bruker denne)
    // -----------------------------
    loadSession: async (id: string): Promise<void> => {
      await runLoadSession(id);
    },

    // -----------------------------
    // Gammel action (alias til loadSession)
    // -----------------------------
    fetchSession: async (id: string): Promise<void> => {
      await runLoadSession(id);
    },
  };
});
