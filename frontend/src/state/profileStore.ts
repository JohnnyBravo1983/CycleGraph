// frontend/src/state/profileStore.ts
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

// ✅ PATCH: commit options
type CommitOptions = {
  markOnboarded?: boolean;
};

type ProfileState = {
  draft: ProfileDraft;
  loading: boolean;
  error: string | null;

  init: () => Promise<void>;
  setDraft: (next: Partial<ProfileDraft> | ((prev: ProfileDraft) => ProfileDraft)) => void;
  applyDefaults: () => void;

  // ✅ Viktig: dette skal faktisk lagre til backend
  commit: (opts?: CommitOptions) => Promise<boolean>;
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

function buildProfileSaveBody(profileToSave: Record<string, unknown>): { profile: Record<string, unknown> } {
  // backend router normaliserer, men vi sender riktig format uansett
  const profile: Record<string, unknown> = {};

  const rider_weight_kg = profileToSave["rider_weight_kg"];
  const bike_weight_kg = profileToSave["bike_weight_kg"];
  const cda = profileToSave["cda"];
  const crr = profileToSave["crr"];
  const crank_efficiency = profileToSave["crank_efficiency"];
  const crank_eff_pct = profileToSave["crank_eff_pct"];
  const bike_type = profileToSave["bike_type"];
  const tire_width_mm = profileToSave["tire_width_mm"];
  const tire_quality = profileToSave["tire_quality"];
  const device = profileToSave["device"];
  const onboarded = profileToSave["onboarded"];

  if (typeof rider_weight_kg === "number") profile.rider_weight_kg = rider_weight_kg;
  if (typeof bike_weight_kg === "number") profile.bike_weight_kg = bike_weight_kg;

  if (typeof cda === "number") profile.cda = cda;
  if (typeof crr === "number") profile.crr = crr;

  if (typeof crank_efficiency === "number") profile.crank_efficiency = crank_efficiency;
  if (typeof crank_eff_pct === "number") profile.crank_eff_pct = crank_eff_pct;

  if (typeof bike_type === "string" && bike_type) profile.bike_type = bike_type;
  if (typeof tire_width_mm === "number") profile.tire_width_mm = tire_width_mm;
  if (typeof tire_quality === "string" && tire_quality) profile.tire_quality = tire_quality;

  // ✅ onboarded flag (bare hvis true)
  if (onboarded === true) profile.onboarded = true;

  profile.device = typeof device === "string" && device ? device : "strava";

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

  commit: async (opts?: CommitOptions) => {
    const draft = get().draft;

    // 🔍 DEBUG (kan beholdes litt til)
    console.log("[profileStore.commit] draft =", draft);

    set({ loading: true, error: null });
    try {
      // ✅ PATCH: onboarded flag (kun når opts.markOnboarded === true)
      const markOnboarded = opts?.markOnboarded === true;

      // draft er ProfileDraft, vi sprer den inn som values (inkl nulls/undefined),
      // men buildProfileSaveBody plukker kun gyldige felt + onboarded=true
      const profileToSave: Record<string, unknown> = {
        ...(draft ?? {}),
        ...(markOnboarded ? { onboarded: true } : {}),
      };

      const body = buildProfileSaveBody(profileToSave);
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
