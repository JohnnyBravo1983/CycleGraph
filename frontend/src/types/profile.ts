// frontend/src/types/profile.ts

/** Brukerprofil brukt for kalibrering/samtykke + analyseparametre. */
export interface UserProfile {
  user_id: string;

  /** S14 – samtykke (lagres hvis relevant) */
  consent_version?: string;
  consent_time?: string; // ISO date-time

  /** Schema-versjon (v0.7.x) */
  schema_version: string;

  // ─────────────────────────────────────────────────────────────
  // MVP – fysiske profilparametre (valgfri nå, så ingenting knekker)
  // ─────────────────────────────────────────────────────────────
  weight_kg?: number;
  cda?: number;
  crr?: number;
  crank_efficiency?: number; // 0..1
}

/**
 * En “editable” profil som UI kan jobbe med uten å ha user_id/schema.
 * (Vi holder det separat så UI alltid kan ha defaults.)
 */
export type UserProfileDraft = {
  weight_kg: number;
  cda: number;
  crr: number;
  crank_efficiency: number;
};

export const DEFAULT_PROFILE: UserProfileDraft = {
  weight_kg: 85,
  cda: 0.30,
  crr: 0.004,
  crank_efficiency: 0.97,
};

export function clampProfile(p: UserProfileDraft): UserProfileDraft {
  return {
    weight_kg: Math.max(40, Math.min(140, p.weight_kg)),
    cda: Math.max(0.15, Math.min(0.60, p.cda)),
    crr: Math.max(0.001, Math.min(0.02, p.crr)),
    crank_efficiency: Math.max(0.85, Math.min(1.0, p.crank_efficiency)),
  };
}

/**
 * Konverter en UserProfile (som kan mangle nye felt) til en UI-draft med defaults.
 */
export function toDraft(profile?: Partial<UserProfile> | null): UserProfileDraft {
  return clampProfile({
    weight_kg: typeof profile?.weight_kg === "number" ? profile!.weight_kg : DEFAULT_PROFILE.weight_kg,
    cda: typeof profile?.cda === "number" ? profile!.cda : DEFAULT_PROFILE.cda,
    crr: typeof profile?.crr === "number" ? profile!.crr : DEFAULT_PROFILE.crr,
    crank_efficiency:
      typeof profile?.crank_efficiency === "number" ? profile!.crank_efficiency : DEFAULT_PROFILE.crank_efficiency,
  });
}

/**
 * Pakk en draft tilbake inn i UserProfile (for lagring).
 * NB: Hvis du ikke har ekte auth ennå, bruker vi “local” user_id og schema_version.
 */
export function fromDraft(draft: UserProfileDraft, base?: Partial<UserProfile> | null): UserProfile {
  return {
    user_id: base?.user_id ?? "local",
    schema_version: base?.schema_version ?? "v0.7.0",
    consent_time: base?.consent_time,
    consent_version: base?.consent_version,
    ...clampProfile(draft),
  };
}
