// frontend/src/state/profileStore.ts
import { create } from "zustand";
import type { UserProfile, UserProfileDraft } from "../types/profile";
import { DEFAULT_PROFILE, clampProfile, toDraft, fromDraft } from "../types/profile";

const LS_KEY = "cg.profile.v1";

type ProfileState = {
  profile: UserProfile | null;
  draft: UserProfileDraft;
  loading: boolean;
  error: string | null;

  init: () => Promise<void>;
  setDraft: (patch: Partial<UserProfileDraft>) => void;
  applyDefaults: () => void;
  commit: () => Promise<boolean>;
};

export const useProfileStore = create<ProfileState>((set, get) => ({
  profile: null,
  draft: { ...DEFAULT_PROFILE },
  loading: false,
  error: null,

  init: async () => {
    set({ loading: true, error: null });
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) {
        set({ loading: false, profile: null, draft: { ...DEFAULT_PROFILE } });
        return;
      }
      const json = JSON.parse(raw) as UserProfile;
      set({ loading: false, profile: json, draft: toDraft(json) });
    } catch (e) {
      set({
        loading: false,
        error: `Kunne ikke lese profil: ${(e as Error).message}`,
        profile: null,
        draft: { ...DEFAULT_PROFILE },
      });
    }
  },

  setDraft: (patch) => {
    const next = clampProfile({ ...get().draft, ...patch });
    set({ draft: next });
  },

  applyDefaults: () => set({ draft: { ...DEFAULT_PROFILE } }),

  commit: async () => {
    set({ loading: true, error: null });
    try {
      const draft = clampProfile(get().draft);
      const current = get().profile;
      const next = fromDraft(draft, current);

      localStorage.setItem(LS_KEY, JSON.stringify(next));
      set({ loading: false, profile: next, draft });
      return true;
    } catch (e) {
      set({ loading: false, error: `Kunne ikke lagre profil: ${(e as Error).message}` });
      return false;
    }
  },
}));
