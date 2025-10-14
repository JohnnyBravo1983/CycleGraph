// frontend/src/tests/state.test.ts
import { describe, it, expect } from "vitest";
import {
  isFirstOutdoorSession,
  isHROnly,
  shouldShowCalibrationModal,
  getCalibrationLabel,
} from "../lib/state";

describe("state helpers", () => {
  it("isHROnly oppdager HR-only via flags og data", () => {
    expect(isHROnly({ flags: { hr_only: true } })).toBe(true);
    expect(isHROnly({ series: { hr: [1, 2], watts: [] } })).toBe(true);
    expect(isHROnly({ series: { hr: [1], watts: undefined } })).toBe(true);
    expect(isHROnly({ series: { hr: [], watts: [100] } })).toBe(false);
  });

  it("isFirstOutdoorSession krever outdoor + flagg", () => {
    expect(isFirstOutdoorSession({ type: "outdoor", meta: { is_first_outdoor: true } })).toBe(true);
    expect(isFirstOutdoorSession({ type: "outdoor", context: { first_outdoor: true } })).toBe(true);
    expect(isFirstOutdoorSession({ type: "outdoor", labels: ["first_outdoor"] })).toBe(true);
    expect(isFirstOutdoorSession({ type: "outdoor" })).toBe(false);
    expect(isFirstOutdoorSession({ type: "indoor", meta: { is_first_outdoor: true } })).toBe(false);
  });

  it("shouldShowCalibrationModal følger regler for kalibrering", () => {
    const base = { type: "outdoor", meta: { is_first_outdoor: true } };

    // Ikke kalibrert → vis modal
    expect(shouldShowCalibrationModal({ ...base, calibrated: null })).toBe(true);
    expect(shouldShowCalibrationModal({ ...base, calibrated: false })).toBe(true);

    // Kalibrert → vises ikke
    expect(shouldShowCalibrationModal({ ...base, calibrated: true })).toBe(false);

    // HR-only → vises ikke
    expect(shouldShowCalibrationModal({ ...base, series: { hr: [1], watts: [] } })).toBe(false);

    // Ikke første outdoor → vises ikke
    expect(shouldShowCalibrationModal({ type: "outdoor", calibrated: false })).toBe(false);
  });

  it("getCalibrationLabel gir riktig tekst", () => {
    expect(getCalibrationLabel({ calibrated: true })).toBe("Kalibrert");
    expect(getCalibrationLabel({ calibrated: false })).toBe("Ikke kalibrert");
    expect(getCalibrationLabel({})).toBe("Ukjent");
  });
});
