import { describe, it, expect } from "vitest";
import {
  formatNP,
  formatIF,
  formatVI,
  formatPaHr,
  formatWattsPerBeat,
  formatCGS,
} from "./formatters";

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
});
