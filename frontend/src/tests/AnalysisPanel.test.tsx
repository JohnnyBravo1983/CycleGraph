// frontend/src/tests/AnalysisPanel.test.tsx
import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import AnalysisPanel from "../components/AnalysisPanel";
import type { PanelSeries } from "../components/AnalysisPanel";

describe("AnalysisPanel", () => {
  it("render FULL uten krasj, viser badges, tooltip og CI-tilgjengelig", () => {
    const seriesFull: PanelSeries = {
      t: [0, 1, 2, 3],
      watts: [220, 215, 222, 218],
      hr: [100, 102, 98, 101],
      precision_watt_ci: { lower: [210, 208], upper: [230, 232] },
      source: "API",
      calibrated: true,
      status: "FULL",
    };

    render(<AnalysisPanel series={seriesFull} />);

    // Kildebadge
    expect(screen.getByTestId("panel-source")).toHaveTextContent(/API/);

    // Kalibreringsbadge
    const calibBadge = screen.getByTestId("calibration-badge");
    expect(calibBadge).toHaveTextContent(/Kalibrert:\s*Ja/i);
    expect(calibBadge).toHaveAttribute(
      "title",
      "Økten er kalibrert. Målingene tar hensyn til CdA og Crr."
    );

    // CI-toggle tilgjengelig
    const ciToggle = screen.getByLabelText(/CI-bånd/i) as HTMLInputElement;
    expect(ciToggle).toBeEnabled();
  });

  // ✅ OPPDATERT: HR-only viser alltid "Kalibrert: –" og HR-only-tooltip
  it("render HR-only uten krasj, skjuler CI og viser kalibrert tooltip", () => {
    const hrOnlySeries: PanelSeries = {
      t: [0, 1, 2],
      hr: [100, 102, 98],
      watts: [], // HR-only
      precision_watt_ci: undefined,
      source: "Mock",
      calibrated: true, // spiller ingen rolle – HR-only overstyrer
      status: "HR-only",
    };

    render(<AnalysisPanel series={hrOnlySeries} />);

    const calibBadge = screen.getByTestId("calibration-badge");
    // Badge skal vise 'Kalibrert: –' ved HR-only
    expect(calibBadge).toHaveTextContent(/Kalibrert:\s*–/i);
    // Tooltip skal være HR-only-forklaringen
    expect(calibBadge).toHaveAttribute(
      "title",
      "Denne økten har bare pulsdata (ingen wattmåler). Kalibrering er ikke aktuelt."
    );

    // CI-toggle skal være disabled (ingen CI)
    const ciToggle = screen.getByLabelText(/CI-bånd/i) as HTMLInputElement;
    expect(ciToggle).toBeDisabled();
  });

  it("render LIMITED (kun watts) uten krasj", () => {
    const seriesLimited: PanelSeries = {
      t: [0, 1, 2],
      watts: [210, 205, 215],
      hr: [],
      precision_watt_ci: undefined,
      source: "API",
      calibrated: false,
      status: "LIMITED",
    };

    render(<AnalysisPanel series={seriesLimited} />);

    // Kildebadge
    expect(screen.getByTestId("panel-source")).toHaveTextContent(/API/);

    // Kalibreringsbadge tekst
    const calibBadge = screen.getByTestId("calibration-badge");
    expect(calibBadge).toHaveTextContent(/Kalibrert:\s*Nei/i);
    expect(calibBadge).toHaveAttribute(
      "title",
      "Denne økten er ikke kalibrert. Kalibrering gir mer presise målinger av luft- og rullemotstand."
    );
  });

  // ✅ OPPDATERT: Ikke-HR-only + calibrated = undefined => ukjent-tooltip
  it("tåler manglende calibrated (undefined) og viser 'Kalibrert: –' m/ukjent-tooltip", () => {
    const seriesUnknown: PanelSeries = {
      t: [0, 1, 2],
      watts: [210, 205, 215], // ikke HR-only (har power)
      hr: [],                 // LIMITED
      precision_watt_ci: undefined,
      source: "API",
      calibrated: undefined,  // ukjent
      status: "LIMITED",
    };

    render(<AnalysisPanel series={seriesUnknown} />);

    const calibBadge = screen.getByTestId("calibration-badge");
    expect(calibBadge).toHaveTextContent(/Kalibrert:\s*–/i);
    expect(calibBadge).toHaveAttribute(
      "title",
      "Kalibreringsstatus er ukjent for denne økten."
    );
  });
});
