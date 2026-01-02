import { create } from "zustand";
import { cgApi } from "../lib/cgApi";

export type ProfileDraft = {
  rider_weight_kg?: number | null;
  bike_weight_kg?: number | null;

  // optional (kan mangle i MVP)
  cda?: number | null;
  crr?: number | null;

  crank_efficiency?: number | null;
  crank_eff_pct?: number | null;

  bike_type?: string | null;
  tire_width_mm?: number | null;
  tire_quality?: string | null;

  device?: string | null;
};

type ProfileGetResp = {
  profile?: Record<string, unknown>;
  profile_version?: string;
  version_hash?: string;
  version_at?: string;
  [k: string]: unknown;
};

type ProfileSaveResp = {
  profile?: Record<string, unknown>;
  profile_version?: string;
  version_hash?: string;
  version_at?: string;
  [k: string]: unknown;
};

type ProfileState = {
  draft: ProfileDraft;
  loading: boolean;
  error: string | null;

  init: () => Promise<void>;
  setDraft: (next: Partial<ProfileDraft> | ((prev: ProfileDraft) => ProfileDraft)) => void;
  applyDefaults: () => void;

  // ✅ Viktig: dette skal faktisk lagre til backend
  commit: () => Promise<boolean>;
};

function toNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function toStr(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v : null;
}

function pickDraftFromProfileObj(profile: Record<string, unknown> | undefined): ProfileDraft {
  const p = profile ?? {};
  return {
    rider_weight_kg: toNum(p["rider_weight_kg"]),
    bike_weight_kg: toNum(p["bike_weight_kg"]),

    cda: toNum(p["cda"]),
    crr: toNum(p["crr"]),

    crank_efficiency: toNum(p["crank_efficiency"]),
    crank_eff_pct: toNum(p["crank_eff_pct"]),

    bike_type: toStr(p["bike_type"]),
    tire_width_mm: toNum(p["tire_width_mm"]),
    tire_quality: toStr(p["tire_quality"]),

    device: toStr(p["device"]) ?? "strava",
  };
}

function buildProfileSaveBody(draft: ProfileDraft): { profile: Record<string, unknown> } {
  // backend router normaliserer, men vi sender riktig format uansett
  const profile: Record<string, unknown> = {};

  if (typeof draft.rider_weight_kg === "number") profile.rider_weight_kg = draft.rider_weight_kg;
  if (typeof draft.bike_weight_kg === "number") profile.bike_weight_kg = draft.bike_weight_kg;

  if (typeof draft.cda === "number") profile.cda = draft.cda;
  if (typeof draft.crr === "number") profile.crr = draft.crr;

  if (typeof draft.crank_efficiency === "number") profile.crank_efficiency = draft.crank_efficiency;
  if (typeof draft.crank_eff_pct === "number") profile.crank_eff_pct = draft.crank_eff_pct;

  if (typeof draft.bike_type === "string" && draft.bike_type) profile.bike_type = draft.bike_type;
  if (typeof draft.tire_width_mm === "number") profile.tire_width_mm = draft.tire_width_mm;
  if (typeof draft.tire_quality === "string" && draft.tire_quality) profile.tire_quality = draft.tire_quality;

  profile.device = typeof draft.device === "string" && draft.device ? draft.device : "strava";

  return { profile };
}

export const useProfileStore = create<ProfileState>((set, get) => ({
  draft: {
    rider_weight_kg: 75,
    bike_weight_kg: 8,
    cda: 0.3,
    crr: 0.004,
    crank_efficiency: 0.96,
    bike_type: "road",
    tire_width_mm: 28,
    tire_quality: "performance",
    device: "strava",
  },
  loading: false,
  error: null,

  setDraft: (next) => {
    if (typeof next === "function") {
      set((state) => ({ draft: next(state.draft) }));
      return;
    }
    set((state) => ({ draft: { ...state.draft, ...next } }));
  },

  applyDefaults: () => {
    set({
      draft: {
        rider_weight_kg: 75,
        bike_weight_kg: 8,
        cda: 0.3,
        crr: 0.004,
        crank_efficiency: 0.96,
        bike_type: "road",
        tire_width_mm: 28,
        tire_quality: "performance",
        device: "strava",
      },
      error: null,
    });
  },

  init: async () => {
    set({ loading: true, error: null });
    try {
      const resp = (await cgApi.profileGet()) as ProfileGetResp;
      const draft = pickDraftFromProfileObj(resp?.profile);
      set({ draft, loading: false, error: null });
      console.log("[profileStore.init] loaded profile_version =", resp?.profile_version, "draft=", draft);
    } catch (e: any) {
      console.warn("[profileStore.init] profileGet failed (using defaults):", e?.message ?? e);
      set({ loading: false, error: null }); // MVP: ikke blokk onboarding hvis profile mangler
    }
  },

  commit: async () => {
    const draft = get().draft;

    // 🔍 DEBUG (kan beholdes litt til)
    console.log("[profileStore.commit] draft =", draft);

    set({ loading: true, error: null });
    try {
      const body = buildProfileSaveBody(draft);
      console.log("[profileStore.commit] profileSave body =", body);

      const saved = (await cgApi.profileSave(body)) as ProfileSaveResp;
      console.log("[profileStore.commit] saved profile_version =", saved?.profile_version, "saved=", saved);

      // Oppdater draft fra backend fasit (hvis backend svarer med profile)
      const nextDraft = pickDraftFromProfileObj(saved?.profile);
      set({ draft: nextDraft, loading: false, error: null });

      return true;
    } catch (e: any) {
      console.error("[profileStore.commit] profileSave failed:", e);
      set({
        loading: false,
        error: e?.message ? String(e.message) : "Klarte ikke å lagre profil.",
      });
      return false;
    }
  },
}));
