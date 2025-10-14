// frontend/src/tests/TrendsChart.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TrendsChart from "../components/TrendsChart";
import React from "react";

const origFetch = global.fetch;

afterEach(() => {
  global.fetch = origFetch;
});

describe("TrendsChart", () => {
  it("renderer uten crash med tom data (API)", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    } as unknown as Response);

    render(<TrendsChart sessionId="none" isMock={false} />);
    expect(await screen.findByText(/Laster trenddata/)).toBeInTheDocument();
    expect(await screen.findByText(/Ingen økter funnet/i)).toBeInTheDocument();
  });

  it("viser NP/PW over tid (mock) og tooltip med riktig info", async () => {
    render(<TrendsChart sessionId="mock-5" isMock />);
    expect(await screen.findByText(/Trender: NP vs PW/)).toBeInTheDocument();

    // Ikke cast til SVGSVGElement – HTMLElement holder for fireEvent
    const svg = await screen.findByRole("img", { name: /Trends NP og PW/i });
    fireEvent.pointerMove(svg, { clientX: 200, clientY: 100 });

    expect(await screen.findByText(/Kilde:/)).toBeInTheDocument();
    expect(screen.getByText(/NP:/)).toBeInTheDocument();
    expect(screen.getByText(/PW:/)).toBeInTheDocument();
  });

  it("viser HR-only fallback når ingen wattdata finnes", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => [
        { id: "a", timestamp: Date.now() - 1_000_000, np: null, pw: null },
        { id: "b", timestamp: Date.now() - 500_000, np: null, pw: null },
      ],
    } as unknown as Response);

    render(<TrendsChart sessionId="a" isMock={false} />);
    expect(await screen.findByText(/Laster trenddata/)).toBeInTheDocument();
    expect(await screen.findByText(/Ingen wattdata tilgjengelig/i)).toBeInTheDocument();
  });

  it("lagger ikke ved mange punkter (rask render, smoke)", async () => {
    render(<TrendsChart sessionId="mock-1" isMock />);
    expect(await screen.findByRole("img", { name: /Trends NP og PW/i })).toBeInTheDocument();
  });
});
