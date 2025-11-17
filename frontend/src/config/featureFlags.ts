// frontend/src/config/featureFlags.ts

// Enkel feature flag for landing-preview.
// Sett VITE_LANDING_PREVIEW=1 i Vercel / .env for å aktivere /landing.
export const isLandingPreviewEnabled: boolean =
  (import.meta as unknown as { env: Record<string, unknown> })?.env?.VITE_LANDING_PREVIEW === "1";