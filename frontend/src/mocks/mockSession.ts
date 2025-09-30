// frontend/src/mocks/mockSession.ts
import type { SessionReport } from "../types/session";

export const mockSession: SessionReport = {
  schema_version: "1.0.0",
  avg_hr: 145,
  calibrated: false,
  status: "ok",

  // ✅ 40 samples → ingen kort-økt (endre til 20 hvis du vil teste kort-økt)
  watts: Array(35).fill(215),

  wind_rel: [0.5, -0.2, 0.1],
  v_rel: [7.1, 6.8, 7.4],

  // Nye felter (S8.5 stubs)
  precision_watt: Array.from({ length: 40 }, (_, i) => 210 + (i % 5)),
  precision_watt_ci: Array.from(
    { length: 40 },
    (_, i) => [190 + (i % 5), 230 + (i % 5)]
  ) as [number, number][],

  sources: ["powermeter", "weather", "profile"],
  cda: null,
  crr: null,
  reason: null,
};