// frontend/src/types/profile.ts

/** Brukerprofil brukt for kalibrering/samtykke i S14. Alle nye felt er valgfrie. */
export interface UserProfile {
  user_id: string;

  /** S14 – samtykke (lagres hvis relevant) */
  consent_version?: string;
  consent_time?: string; // ISO date-time

  /** Schema-versjon (v0.7.x) */
  schema_version: string;
}
