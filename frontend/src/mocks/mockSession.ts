// frontend/src/lib/mockSession.ts
import type { SessionReport } from "../types/session";

export const mockSession: SessionReport = {
  schema_version: "1.0.0",
  avg_hr: 145,
  calibrated: true,
  status: "ok",

  watts: [220, 230, 210, 200], // dummy wattserie
  wind_rel: [0.1, -0.2, 0.0],
  v_rel: [7.1, 6.8, 7.4],

  precision_watt: [215, 225, 212, 205],
  precision_watt_ci: [
    [210, 220],
    [220, 230],
    [210, 215],
    [200, 210],
  ],

  sources: ["powermeter", "weather", "profile"],
  cda: 0.32,
  crr: 0.005,
  reason: null,

  // ───────── S9 nøkkelmetrikker ─────────
  np: 218,
  if_: 0.82,
  vi: 1.05,
  pa_hr: 0.035, // = 3.5 %
  w_per_beat: 1.52,
  cgs: 72.5,
  precision_watt_value: 214,

  // ───────── S9 nye felter ─────────
  mode: "outdoor",
  has_gps: true,
};

// Kort økt – for å trigge short-session guard (<30 samples)
export const mockSessionShort: SessionReport = {
  ...mockSession,
  status: "short_session",
  watts: [200, 210], // bare 2 samples
  precision_watt: [205, 208],
  precision_watt_ci: [
    [200, 210],
    [205, 212],
  ],
  np: 206,
  if_: 0.65,
  vi: 1.02,
  pa_hr: 0.01,
  w_per_beat: 1.3,
  cgs: 40,
  precision_watt_value: 205,
  reason: "short_session",

  // spesifikt for denne: indoor (f.eks. rulle, uten gps)
  mode: "indoor",
  has_gps: false,
};

// Ikke-kalibrert økt – viser calibration_reason
export const mockSessionNoCalib: SessionReport = {
  ...mockSession,
  calibrated: false,
  status: "hr_only_demo",
  precision_watt: null,
  precision_watt_ci: null,
  np: null,
  if_: null,
  vi: null,
  pa_hr: null,
  w_per_beat: null,
  cgs: null,
  precision_watt_value: null,
  reason: "no_power_data",

  // ikke-kalibrert men fortsatt outdoor
  mode: "outdoor",
  has_gps: true,
};