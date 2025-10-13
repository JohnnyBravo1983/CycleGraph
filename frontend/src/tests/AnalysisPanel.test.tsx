import "@testing-library/jest-dom/vitest";
import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import AnalysisPanel from "../components/AnalysisPanel";
import type { AnalysisSeries } from "../components/AnalysisChart";

afterEach(() => cleanup());

// Felles t-akse
const T = Array.from({ length: 120 }, (_, i) => i);

// Utvidet type for å matche AnalysisPanel sine ekstra felt
type SeriesInput = AnalysisSeries & {
  precision_watt_ci?: { lower?: number[]; upper?: number[] };
  status?: string;
};

describe("AnalysisPanel", () => {
  it("render FULL uten krasj, viser badges og CI-tilgjengelig", () => {
    const watts = T.map(() => 210);
    const hr = T.map(() => 145);
    const series: SeriesInput = {
      t: T,
      watts,
      hr,
      precision_watt_ci: { lower: watts.map((w) => w - 12), upper: watts.map((w) => w + 12) },
      source: "mock",
      calibrated: false,
      status: "FULL",
    };
    const utils = render(<AnalysisPanel series={series} />);
    // Mer presise queries for å unngå duplikater
    const sourceBadge = utils.getByTitle("Datakilde");
    expect(sourceBadge).toHaveTextContent("Mock");
    const calibBadge = utils.getByTitle("Kalibreringsstatus");
    expect(calibBadge).toHaveTextContent("Ikke kalibrert");

    expect(utils.getByText("Status")).toBeInTheDocument();
    expect(utils.getByText("FULL")).toBeInTheDocument();

    // CI-info
    expect(utils.getByText("CI-bånd (PW)")).toBeInTheDocument();
    expect(utils.getByText("Tilgjengelig")).toBeInTheDocument();

    // Innebygd graf
    expect(utils.getByTestId("analysis-chart-in-panel")).toBeInTheDocument();
  });

  it("render HR-only uten krasj, skjuler CI", () => {
    const hr = T.map(() => 150);
    const series: SeriesInput = {
      t: T,
      hr,
      source: "api",
      calibrated: true,
      status: "HR-only",
    };
    const utils = render(<AnalysisPanel series={series} />);
    const sourceBadge = utils.getByTitle("Datakilde");
    expect(sourceBadge).toHaveTextContent("API");
    const calibBadge = utils.getByTitle("Kalibreringsstatus");
    expect(calibBadge).toHaveTextContent("Kalibrert");

    expect(utils.getByText("HR-only")).toBeInTheDocument();
    expect(utils.getByText("CI-bånd (PW)")).toBeInTheDocument();
    expect(utils.getByText("Mangler")).toBeInTheDocument();
  });

  it("render LIMITED (kun watts) uten krasj", () => {
    const watts = T.map(() => 200);
    const series: SeriesInput = {
      t: T,
      watts,
      source: "api",
      calibrated: false,
      status: "LIMITED",
    };
    const utils = render(<AnalysisPanel series={series} />);
    expect(utils.getByText("LIMITED")).toBeInTheDocument();
  });
});
