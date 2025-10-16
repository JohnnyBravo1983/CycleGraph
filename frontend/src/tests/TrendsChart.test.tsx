// frontend/src/tests/TrendsChart.test.tsx
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TrendsChart from "../components/TrendsChart";
import React from "react";

const origFetch = global.fetch;

afterEach(() => {
  global.fetch = origFetch;
});

/** Utsatt promise så vi kan styre når fetch-responsen kommer */
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("TrendsChart", () => {
  it("renderer uten crash med tom data (API)", async () => {
    // Mock fetch og utsett respons til etter første render
    const d = deferred<Response>();
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockReturnValueOnce(d.promise as unknown as Promise<Response>);

    render(<TrendsChart sessionId="none" isMock={false} />);

    // Komponent tegner tittel/SVG umiddelbart
    expect(await screen.findByText(/Trender: NP vs PW/i)).toBeInTheDocument();

    // Returnér tom liste (ingen økter)
    d.resolve(new Response(JSON.stringify([]), { status: 200 }));

    // Vi forventer at grafen fortsatt rendres uten krasj
    expect(
      await screen.findByRole("img", { name: /Trends NP og PW/i })
    ).toBeInTheDocument();

    fetchSpy.mockRestore();
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

  it("renderer uten crash når ingen wattdata finnes (HR-only fallback)", async () => {
    // Mock fetch med utsatt respons slik at vi kan verifisere slutt-tilstand
    const d = deferred<Response>();
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockReturnValueOnce(d.promise as unknown as Promise<Response>);

    render(<TrendsChart sessionId="a" isMock={false} />);

    // Tittel finnes umiddelbart (komponenten viser ikke nødvendigvis en loader-tekst)
    expect(await screen.findByText(/Trender: NP vs PW/i)).toBeInTheDocument();

    // Returnér en liste uten wattdata (HR-only)
    const hrOnlyPayload = [
      { id: "a", timestamp: Date.now() - 1_000_000, np: null, pw: null },
      { id: "b", timestamp: Date.now() - 500_000, np: null, pw: null },
    ];
    d.resolve(new Response(JSON.stringify(hrOnlyPayload), { status: 200 }));

    // Forvent at grafen fortsatt rendres uten krasj
    expect(
      await screen.findByRole("img", { name: /Trends NP og PW/i })
    ).toBeInTheDocument();

    fetchSpy.mockRestore();
  });

  it("lagger ikke ved mange punkter (rask render, smoke)", async () => {
    render(<TrendsChart sessionId="mock-1" isMock />);
    expect(
      await screen.findByRole("img", { name: /Trends NP og PW/i })
    ).toBeInTheDocument();
  });
});
