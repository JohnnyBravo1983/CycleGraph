import { create } from "zustand";

type Source = "mock" | "live" | null;

type SessionState = {
  source: Source;
  report: any | null;
  loading: boolean;
  error: string | null;
  fetchSession: (id?: string) => Promise<void>;
};

export const useSessionStore = create<SessionState>((set) => ({
  source: "mock",
  report: null,
  loading: false,
  error: null,
  async fetchSession(id?: string) {
    set({ loading: true, error: null });
    try {
      const url = id ? `/api/session/${id}` : "/mock/session.json";
      const res = await fetch(url);
      const data = await res.json();
      set({ report: data, loading: false });
    } catch (e: any) {
      set({ error: String(e), loading: false });
    }
  },
}));
