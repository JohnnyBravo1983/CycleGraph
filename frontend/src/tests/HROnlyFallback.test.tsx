// frontend/src/tests/HROnlyFallback.test.tsx
import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
// Viktig: utvider expect med jest-dom matchers OG typene for Vitest
import "@testing-library/jest-dom/vitest";

import TrendsChart from "../components/TrendsChart";
import AnalysisPanel from "../components/AnalysisPanel";
import type { PanelSeries } from "../components/AnalysisPanel";

describe("HR-only fallback", () => {
  const hrOnlySeries: PanelSeries = {
    t: [0, 1, 2, 3],
    hr: [100, 102, 98, 101],
    watts: [], // ingen watt
    precision_watt_ci: undefined,
    source: "Mock",
    calibrated: false, // spiller ingen rolle for visningen ved HR-only
    status: "HR-only",
  };

  it("TrendsChart viser tekstlig fallback ved HR-only", () => {
    render(
      <TrendsChart
        sessionId="s1"
        isMock={true}
        series={{ t: hrOnlySeries.t, hr: hrOnlySeries.hr, watts: hrOnlySeries.watts }}
        calibrated={hrOnlySeries.calibrated}
        source="Mock"
        hrOnly={true}
      />
    );

    // Matche robust del av teksten (unngå å låse til hele setningen)
    expect(
      screen.getByText(/bare pulsdata \(ingen wattmåler\)/i)
    ).toBeInTheDocument();
  });

  it("AnalysisPanel viser 'Kalibrert: –' og grå indikator ved HR-only", () => {
    render(<AnalysisPanel series={hrOnlySeries} />);

    // Kalibreringsbadge-tekst
    expect(screen.getByTestId("calibration-badge")).toHaveTextContent(/Kalibrert:\s*–/i);

    // Dot finnes (grå) – verifiser semantisk via label i stedet for CSS-klasse
    expect(screen.getByTestId("calibration-status-dot")).toHaveAttribute(
      "aria-label",
      expect.stringMatching(/ukjent/i) // badge setter "Kalibreringsstatus ukjent" ved HR-only
    );

    // Kildebadge finnes (Mock)
    expect(screen.getByTestId("panel-source")).toHaveTextContent(/Mock/);
  });
});
