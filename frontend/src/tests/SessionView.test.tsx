// frontend/src/tests/SessionView.test.tsx
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import type { SessionReport } from "../types/session";
import type { Profile } from "../lib/schema";

// Stub SessionCard for å unngå komplekse props/render
vi.mock("../components/SessionCard", () => ({
  default: () => <div data-testid="session-card">SessionCard</div>,
}));

// --- Mock av store --------------------------------------------------------
const fetchSessionMock = vi.fn<(id?: string) => Promise<void>>();
const analyzeSessionMock = vi.fn<(id: string) => Promise<void>>();
const saveProfileAndReanalyzeMock = vi.fn<(sessionId: string, profile: Profile) => Promise<void>>();

type Source = "api" | "mock" | null;

type StoreSlice = {
  session: SessionReport | null;
  loading: boolean;
  error: string | null;
  source: Source;
  fetchSession: (id?: string) => Promise<void>;

  // Trinn 2: analyze-state som SessionView forventer
  analyzeResult: unknown;
  analyzeLoading: boolean;
  analyzeError: string | null;
  analyzeSession: (id: string) => Promise<void>;
  saveProfileAndReanalyze: (sessionId: string, profile: Profile) => Promise<void>;
};

let mockedState: StoreSlice = {
  session: null,
  loading: false,
  error: "HTTP 404 Not Found",
  source: "api",
  fetchSession: fetchSessionMock,
  analyzeResult: null,
  analyzeLoading: false,
  analyzeError: null,
  analyzeSession: analyzeSessionMock,
  saveProfileAndReanalyze: saveProfileAndReanalyzeMock,
};

vi.mock("../state/sessionStore", () => ({
  useSessionStore: () => mockedState,
}));

// ✅ Riktig sti fra src/tests → src/routes
import SessionView from "../routes/SessionView";

describe("SessionView", () => {
  beforeEach(() => {
    fetchSessionMock.mockReset();
    analyzeSessionMock.mockReset();
    saveProfileAndReanalyzeMock.mockReset();

    mockedState = {
      session: null,
      loading: false,
      error: "HTTP 404 Not Found",
      source: "api",
      fetchSession: fetchSessionMock,
      analyzeResult: null,
      analyzeLoading: false,
      analyzeError: null,
      analyzeSession: analyzeSessionMock,
      saveProfileAndReanalyze: saveProfileAndReanalyzeMock,
    };
  });

  function renderAt(path = "/session/ABC123") {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/session/:id" element={<SessionView />} />
        </Routes>
      </MemoryRouter>
    );
  }

  it("viser ErrorBanner med 404-tekst og lar oss retrye", () => {
    renderAt("/session/ABC123");

    expect(
      screen.getByText(/Ingen data å vise for denne økten/i)
    ).toBeInTheDocument();

    const retry = screen.getByRole("button", { name: /prøv igjen/i });
    fireEvent.click(retry);
    expect(fetchSessionMock).toHaveBeenCalledWith("ABC123");
  });

  it("viser SessionCard når session finnes", () => {
    mockedState.session = { schema_version: "1.0.0" } as unknown as SessionReport;
    mockedState.error = null;

    renderAt("/session/ABC123");
    expect(screen.getByTestId("session-card")).toBeInTheDocument();
  });

  it("kaller saveProfileAndReanalyze når 'Lagre profil' klikkes og analyzeResult finnes", () => {
    // Minimal fake-analyzeResult med profil-felt
    const fakeAnalyzeResult = {
      source: "api",
      weather_applied: false,
      weather_source: "test",
      profile_version: 1,
      metrics: {
        precision_watt: 250,
        drag_watt: 100,
        rolling_watt: 50,
        total_watt: 250,
        calibration_mae: 5,
        calibrated: true,
        calibration_status: "ok",
        weather_used: false,
        weather_meta: null,
        weather_fp: null,
        profile_used: {
          cda: 0.3,
          crr: 0.004,
          crank_efficiency: 0.96,
          weight_kg: 90,
          bike_type: "road",
          tire_width_mm: 28,
          tire_quality: "good",
          profile_version: 1,
        },
        estimated_error_pct_range: [5, 10],
        precision_quality_hint: "ok",
        profile_completeness: 1,
      },
      profile_used: {
        cda: 0.3,
        crr: 0.004,
        crank_efficiency: 0.96,
        weight_kg: 90,
        bike_type: "road",
        tire_width_mm: 28,
        tire_quality: "good",
        profile_version: 1,
      },
      samples: [],
      publish: {},
    };

    mockedState.error = null;
    mockedState.analyzeResult = fakeAnalyzeResult;

    renderAt("/session/ABC123");

    const btn = screen.getByRole("button", { name: /lagre profil/i });
    expect(btn).toBeEnabled();

    btn.click();

    expect(saveProfileAndReanalyzeMock).toHaveBeenCalledTimes(1);
    expect(saveProfileAndReanalyzeMock).toHaveBeenCalledWith(
      "ABC123",
      expect.any(Object)
    );
  });
});