import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom/vitest"; // gir .toBeInTheDocument matchere og riktig typing
import { render, screen } from "@testing-library/react";
import SessionCard from "../components/SessionCard";
import type React from "react";

// Typen SessionCard forventer på `session`-prop
type SessionCardSession = React.ComponentProps<typeof SessionCard>["session"];

// Hjelper for å gi CI-overstyring uten type-kollisjon
function withCI(low: number, high: number): Partial<SessionCardSession> {
  // SessionCard støtter tuple/objekt; vi leverer tuple og caster via unknown -> Partial
  return { precision_watt_ci: [low, high] as [number, number] } as unknown as Partial<SessionCardSession>;
}

// Base-session uten any, med påkrevde felt (inkl. status)
function baseSession(overrides: Partial<SessionCardSession> = {}): SessionCardSession {
  const base: SessionCardSession = {
    // 30 samples (unngår short-session warning)
    watts: [
      100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
      110, 111, 112, 113, 114, 115, 116, 117, 118, 119,
      120, 121, 122, 123, 124, 125, 126, 127, 128, 129,
    ],
    calibrated: true,
    mode: "outdoor",
    status: "FULL",           // <-- krav i SessionReport
    np: 250,
    if_: 0.85,
    vi: 1.06,
    pa_hr: 4.2,
    w_per_beat: 1.45,
    cgs: 76.2,
    precision_watt_value: 262,

    // Hjelpefelt dersom strengere typer finnes i prosjektet
    schema_version: "0.7.3",
    avg_hr: null,
  };

  return { ...base, ...overrides };
}

describe("SessionCard – Trinn 6", () => {
  it("viser publish-pill ✓ når publish_state=done", () => {
    render(<SessionCard session={baseSession({ publish_state: "done" })} />);
    const pill = screen.getByTestId("publish-pill");
    expect(pill.textContent).toContain("✓");
    expect(pill.textContent?.toLowerCase()).toContain("published");
  });

  it("viser PW CI når precision_watt_ci finnes", () => {
    render(<SessionCard session={baseSession(withCI(248, 276))} />);
    expect(screen.getByText(/PW CI/i)).toBeInTheDocument();
    expect(screen.getByText(/248–276 W/i)).toBeInTheDocument();
  });

  it("viser CdA, Crr, vekt og dekk", () => {
    render(
      <SessionCard
        session={baseSession({
          CdA: 0.291,
          crr_used: 0.0035,
          rider_weight: 93,
          bike_weight: 8.4,
          tire_width: 28,
          bike_type: "road",
        })}
      />
    );
    expect(screen.getByText(/CdA/i).nextSibling?.textContent).toMatch(/0\.291 m²/);
    expect(screen.getByText(/Crr/i).nextSibling?.textContent).toMatch(/0\.0035/);
    expect(screen.getByText(/Rytter/i).nextSibling?.textContent).toMatch(/93 kg/);
    expect(screen.getByText(/Sykkel/i).nextSibling?.textContent).toMatch(/8\.4 kg/);
    expect(screen.getByText(/Dekkbredde/i).nextSibling?.textContent).toMatch(/28 mm/);
    expect(screen.getByText(/Type/i).nextSibling?.textContent).toMatch(/road/);
  });

  it("viser indoor-hint når reason=indoor_session", () => {
    render(
      <SessionCard
        session={baseSession({
          reason: "indoor_session",
          calibrated: false,
          calibration_reason: "indoor_session",
        })}
      />
    );
    expect(screen.getByText(/Rulleøkt – ikke kalibrert/i)).toBeInTheDocument();
  });

  it("viser Publisert med lokal dato når publish_time finnes", () => {
    render(<SessionCard session={baseSession({ publish_time: "2025-10-22T08:00:00.000Z" })} />);
    expect(screen.getByText("Publisert")).toBeInTheDocument();
    // ikke asserte eksakt streng (lokale formater varierer), bare at feltet ikke er "—"
    const publishedVal = screen.getByText("Publisert").parentElement?.querySelector("div.mt-1");
    expect(publishedVal?.textContent).not.toBe("—");
  });
});
