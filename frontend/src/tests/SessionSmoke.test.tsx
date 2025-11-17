// frontend/src/tests/SessionSmoke.test.tsx
import "@testing-library/jest-dom/vitest";
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// 🧪 Mocker store slik at vi kan styre session/loading/error
type StoreState = {
  session: unknown;
  loading: boolean;
  error: string | null;
  fetchSession: (id: string) => void;

  // Trinn 2: analyze-state som SessionView forventer
  analyzeResult: unknown;
  analyzeLoading: boolean;
  analyzeError: string | null;
  analyzeSession: (id: string) => Promise<void>;
};

const storeState: StoreState = {
  session: null,
  loading: false,
  error: null,
  fetchSession: vi.fn(),

  analyzeResult: null,
  analyzeLoading: false,
  analyzeError: null,
  analyzeSession: vi.fn(async () => {}),
};

// Viktig: mock-path må matche importen brukt i SessionView (../state/sessionStore)
vi.mock("../state/sessionStore", () => {
  return {
    useSessionStore: () => storeState,
  };
});

// Importer etter mock
import SessionView from "../routes/SessionView";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/session/:id" element={<SessionView />} />
      </Routes>
    </MemoryRouter>
  );
}

// Hjelpere for datasett
const T = Array.from({ length: 120 }, (_, i) => i);

function makeFullSession() {
  return {
    schema_version: "1",
    watts: T.map(() => 210),
    hr: T.map(() => 145),
    calibrated: true,
    status: "FULL",
    wind_rel: 0,
    v_rel: 0,
  };
}
function makeHrOnlySession() {
  return {
    schema_version: "1",
    hr: T.map(() => 150),
    calibrated: false,
    status: "HR-only",
    wind_rel: 0,
    v_rel: 0,
  };
}
function makeLimitedSession() {
  return {
    schema_version: "1",
    watts: T.map(() => 200),
    calibrated: false,
    status: "LIMITED",
    wind_rel: 0,
    v_rel: 0,
  };
}

beforeEach(() => {
  storeState.session = null;
  storeState.loading = false;
  storeState.error = null;
  storeState.fetchSession = vi.fn();

  storeState.analyzeResult = null;
  storeState.analyzeLoading = false;
  storeState.analyzeError = null;
  storeState.analyzeSession = vi.fn(async () => {});
});

afterEach(() => {
  cleanup();
});

describe("SessionView smoke", () => {
  it("viser AnalysisPanel for FULL", async () => {
    storeState.session = makeFullSession();
    const utils = renderAt("/session/ABC123");
    expect(await screen.findByText("Økt")).toBeInTheDocument();
    expect(utils.getByTestId("analysis-panel")).toBeInTheDocument();
  });

  it("viser HR-only panel uten CI", async () => {
    storeState.session = makeHrOnlySession();
    const utils = renderAt("/session/XYZ");
    expect(await screen.findByText("HR-only")).toBeInTheDocument();
    expect(utils.getByText("CI-bånd (PW)")).toBeInTheDocument();
    expect(utils.getByText("Mangler")).toBeInTheDocument();
  });

  it("viser LIMITED panel", async () => {
    storeState.session = makeLimitedSession();
    const utils = renderAt("/session/LIM");
    expect(await screen.findByText("LIMITED")).toBeInTheDocument();
    expect(utils.getByTestId("analysis-panel")).toBeInTheDocument();
  });

  it("viser ErrorBanner ved 404/500/timeout", async () => {
    // 404
    storeState.session = null;
    storeState.error = "HTTP 404 Not Found";
    let utils = renderAt("/session/ERR404");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getAllByText(/Ingen data å vise/).length).toBeGreaterThan(0);
    utils.unmount();

    // 500
    storeState.session = null;
    storeState.error = "HTTP 500 Internal Server Error";
    utils = renderAt("/session/ERR500");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getAllByText(/Noe gikk galt/).length).toBeGreaterThan(0);
    utils.unmount();

    // Timeout
    storeState.session = null;
    storeState.error = "Tidsavbrudd";
    utils = renderAt("/session/ERRTO");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getAllByText(/Kunne ikke hente data/).length).toBeGreaterThan(0);
    utils.unmount();
  });

  it("viser ikke panel når både watts og hr mangler", async () => {
    storeState.session = {
      schema_version: "1",
      wind_rel: 0,
      v_rel: 0,
      calibrated: false,
      status: "LIMITED",
    };
    const utils = renderAt("/session/NODATA");
    expect(utils.queryByTestId("analysis-panel")).toBeNull();
  });
});
