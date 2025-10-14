// frontend/src/tests/formatters.test.ts
import { describe, it, expect, vi } from "vitest";
import {
  formatNP,
  formatIF,
  formatVI,
  formatPaHr,
  formatWattsPerBeat,
  formatCGS,
  formatCalibrationStatus,
  formatTrendTimestamp,
  formatPW,
  formatTooltip,
  formatCI,
  formatTime,
} from "../lib/formatters";

describe("formatters", () => {
  it("formatNP", () => {
    const s = formatNP(205.4);
    expect(s).toMatch(/205\D*W/);
    expect(formatNP(0)).toMatch(/0\D*W/);
    expect(formatNP(null)).toBe("—");
    expect(formatNP(undefined, { fallback: "N/A" })).toBe("N/A");
    expect(formatNP(NaN as unknown as number)).toBe("—");
  });

  it("formatIF", () => {
    const s = formatIF(0.654);
    expect(s.includes("0,65")).toBe(true);
    expect(formatIF(null)).toBe("—");
  });

  it("formatVI", () => {
    expect(formatVI(1.023)).toContain("1,02");
    expect(formatVI(undefined)).toBe("—");
  });

  it("formatPaHr", () => {
    const pos = formatPaHr(1.0);
    expect(pos.includes("1,0")).toBe(true);
    expect(pos.includes("%")).toBe(true);

    const neg = formatPaHr(-0.5);
    expect(neg.includes("0,5")).toBe(true);
    expect(neg.includes("%")).toBe(true);

    expect(formatPaHr(null)).toBe("—");
  });

  it("formatWattsPerBeat", () => {
    const s = formatWattsPerBeat(1.296);
    expect(s).toContain("1,30");
    expect(s).toMatch(/W\/slag$/);
    expect(formatWattsPerBeat(undefined)).toBe("—");
  });

  it("formatCGS", () => {
    expect(formatCGS(40)).toBe("40,0");
    expect(formatCGS(40.04)).toBe("40,0");
    expect(formatCGS(40.05)).toBe("40,1");
    expect(formatCGS(null)).toBe("—");
  });

  /* ────────────────────────────────────────────────────────────
   * Nye tester – Sprint 12
   * ────────────────────────────────────────────────────────────
   */

  it("formatCalibrationStatus", () => {
    expect(formatCalibrationStatus(true)).toBe("Kalibrert");
    expect(formatCalibrationStatus(false)).toBe("Ikke kalibrert");
    expect(formatCalibrationStatus(null)).toBe("Ukjent");
  });

  it("formatTrendTimestamp – håndterer datoer riktig", () => {
    const now = new Date("2025-10-14T12:00:00Z");
    vi.setSystemTime(now);

    const sameDay = new Date("2025-10-14T08:15:30Z").toISOString();
    const result1 = formatTrendTimestamp(sameDay);
    expect(result1).toMatch(/\d{2}:\d{2}:\d{2}/);

    // Bruk en dato som garantert havner på en annen dag lokalt
    const otherDay = new Date("2025-10-10T22:01:00Z").toISOString();
    const result2 = formatTrendTimestamp(otherDay);

    // Aksepter både klokkeslett og dato+tid (tidssoneuavhengig)
    expect(result2).toMatch(/\d{2}:\d{2}(:\d{2})?|(\d{2}\.\d{2} \d{2}:\d{2})/);

    const invalid = formatTrendTimestamp("not-a-date");
    expect(invalid).toBe("—");

    vi.useRealTimers();
  });

  it("formatPW", () => {
    expect(formatPW(3.14)).toBe("3,1 W/beat");
    expect(formatPW(null)).toBe("—");
  });

  it("formatTooltip", () => {
    expect(formatTooltip("api", true)).toBe("Kilde: API – Kalibrert: Ja");
    expect(formatTooltip("mock", false)).toBe("Kilde: Mock – Kalibrert: Nei");
  });

  it("formatCI", () => {
    expect(formatCI(100, 120)).toBe("±10 watt");
    expect(formatCI(120, 100)).toBe("±10 watt");
    expect(formatCI(null, 100)).toBe("Mangler");
    expect(formatCI(100, null)).toBe("Mangler");
    expect(formatCI(undefined, undefined)).toBe("Mangler");
  });

  it("formatTime", () => {
    expect(formatTime(0)).toBe("00:00");
    expect(formatTime(75)).toBe("01:15");
    expect(formatTime(3661)).toBe("01:01:01");
    expect(formatTime(null)).toBe("—");
  });
});
