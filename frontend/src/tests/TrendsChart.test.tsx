// frontend/src/tests/TrendsChart.test.tsx

import "@testing-library/jest-dom/vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  type Mock,
} from "vitest";
import TrendsChart from "../components/TrendsChart";
import { getTrendSummary, getTrendPivot } from "../lib/api";

// Mock api.ts → getTrendSummary / getTrendPivot
vi.mock("../lib/api", () => {
  return {
    getTrendSummary: vi.fn(),
    getTrendPivot: vi.fn(),
  };
});

describe("TrendsChart", () => {
  beforeEach(() => {
    (getTrendSummary as Mock).mockReset();
    (getTrendPivot as Mock).mockReset();
  });

  it("vises fallback når summary.csv er tom", async () => {
    (getTrendSummary as Mock).mockResolvedValue({
      rows: [],
    });

    (getTrendPivot as Mock).mockResolvedValue({
      rows: [],
    });

    render(<TrendsChart sessionId="trend-empty" isMock={false} />);

    await waitFor(() =>
      expect(screen.getByTestId("trend-empty")).toBeInTheDocument()
    );
  });

  it("rendrer trendpunkter når summary.csv har data", async () => {
    (getTrendSummary as Mock).mockResolvedValue({
      rows: [
        [
          "date",
          "session_id",
          "avg_watt",
          "avg_hr",
          "w_per_beat",
          "cda_used",
          "crr_used",
        ],
        ["2025-11-01", "ride1", "220", "150", "1.5", "0.30", "0.004"],
        ["2025-11-02", "ride2", "230", "152", "1.6", "0.30", "0.004"],
      ],
    });

    (getTrendPivot as Mock).mockResolvedValue({
      rows: [
        ["weather_source", "mean", "std", "count"],
        ["open_meteo", "225", "5", "2"],
      ],
    });

    render(<TrendsChart sessionId="trend-has-data" isMock={false} />);

    await waitFor(() =>
      expect(screen.getByTestId("trend-summary")).toBeInTheDocument()
    );

    // Sjekk at minst én rad er rendret
    const items = screen.getAllByRole("listitem");
    expect(items.length).toBeGreaterThan(0);
  });

  it("viser pivotseksjon når pivot.csv har data", async () => {
    (getTrendSummary as Mock).mockResolvedValue({
      rows: [
        [
          "date",
          "session_id",
          "avg_watt",
          "avg_hr",
          "w_per_beat",
          "cda_used",
          "crr_used",
        ],
        ["2025-11-01", "ride1", "220", "150", "1.5", "0.30", "0.004"],
      ],
    });

    (getTrendPivot as Mock).mockResolvedValue({
      rows: [
        ["weather_source", "mean", "std", "count"],
        ["open_meteo", "225", "5", "2"],
        ["frozen", "230", "3", "1"],
      ],
    });

    render(<TrendsChart sessionId="trend-pivot" isMock={false} />);

    await waitFor(() =>
      expect(screen.getByTestId("trend-pivot")).toBeInTheDocument()
    );
  });
});
