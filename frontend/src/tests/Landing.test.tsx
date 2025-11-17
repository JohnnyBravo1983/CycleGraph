// frontend/src/tests/Landing.test.tsx
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, type Mock } from "vitest";
import "@testing-library/jest-dom"; // Importer jest-dom for å få tilgang til .toBeInTheDocument()
import { Landing } from "../landing";
import { SEO } from "../landing/SEO";

vi.mock("../lib/api", () => {
  return {
    getTrendSummary: vi.fn(),
  };
});

const { getTrendSummary } = await import("../lib/api");

describe("Landing page", () => {
  beforeEach(() => {
    (getTrendSummary as Mock).mockReset();
    document.head.innerHTML = "";
    document.title = "";
  });

  it("renderer hero-seksjonen med tittel og CTA", () => {
    (getTrendSummary as Mock).mockResolvedValueOnce({});

    render(<Landing />);

    expect(
      screen.getByText(/Få kontroll på watt, puls/i)
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: /Bli med i beta-listen/i })
    ).toBeInTheDocument();
  });

  it("setter grunnleggende SEO-tags og JSON-LD", () => {
    render(<SEO />);

    expect(document.title).toContain("CycleGraph");

    const metaDesc = document.querySelector('meta[name="description"]');
    expect(metaDesc).not.toBeNull();
    expect(metaDesc?.getAttribute("content")).toContain("CycleGraph");

    const ogTitle = document.querySelector('meta[property="og:title"]');
    expect(ogTitle).not.toBeNull();
    expect(ogTitle?.getAttribute("content")).toContain("CycleGraph");

    const jsonLd = document.querySelector('script[type="application/ld+json"]');
    expect(jsonLd).not.toBeNull();
  });

  it("viser ok-status når trend-endepunktet svarer", async () => {
    (getTrendSummary as Mock).mockResolvedValueOnce({ any: "value" });

    render(<Landing />);

    await waitFor(() => {
      expect(
        screen.getByTestId("landing-trend-ok")
      ).toBeInTheDocument();
    });
  });

  it("viser error-status når trend-endepunktet feiler", async () => {
    (getTrendSummary as Mock).mockRejectedValueOnce(new Error("fail"));

    render(<Landing />);

    await waitFor(() => {
      expect(
        screen.getByTestId("landing-trend-error")
      ).toBeInTheDocument();
    });
  });
});