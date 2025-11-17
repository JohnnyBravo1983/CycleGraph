// frontend/src/tests/SessionsList.test.tsx
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import type { SessionInfo } from "../types/session";

// --- Lokal mock-state-type for å unngå `any` -------------------------------

type MockSessionStoreState = {
  sessions: SessionInfo[] | null;
  sessionsLoading: boolean;
  sessionsError: string | null;
  fetchSessionsList: () => Promise<void>;
};

// --- Mocker verdier --------------------------------------------------------

let mockSessions: SessionInfo[] | null = null;
let mockLoading = false;
let mockError: string | null = null;

// NB: Vitest fn tar én typeparameter: selve funksjonstypen
const fetchSessionsListMock = vi.fn<() => Promise<void>>(async () => {});

// --- Mock av useSessionStore -----------------------------------------------

vi.mock("../state/sessionStore", () => {
  return {
    useSessionStore: (
      selector: (state: MockSessionStoreState) => unknown
    ) =>
      selector({
        sessions: mockSessions,
        sessionsLoading: mockLoading,
        sessionsError: mockError,
        fetchSessionsList: fetchSessionsListMock,
      }),
  };
});

// Etter mock: importer komponenten vi tester
import SessionsList from "../routes/SessionsList";

// --- Hjelpefunksjon for å sette opp Router ---------------------------------

function renderWithRouter() {
  return render(
    <MemoryRouter initialEntries={["/sessions"]}>
      <Routes>
        <Route path="/sessions" element={<SessionsList />} />
        {/* dummy-sessionroute – vi sjekker bare href */}
        <Route
          path="/session/:id"
          element={<div data-testid="session-view">SessionView</div>}
        />
      </Routes>
    </MemoryRouter>
  );
}

// --- Tester ----------------------------------------------------------------

describe("SessionsList", () => {
  beforeEach(() => {
    mockSessions = null;
    mockLoading = false;
    mockError = null;
    fetchSessionsListMock.mockClear();
  });

  it("kaller fetchSessionsList ved mount", () => {
    renderWithRouter();
    expect(fetchSessionsListMock).toHaveBeenCalledTimes(1);
  });

  it("viser tom-liste melding når ingen økter", async () => {
    mockSessions = [];
    renderWithRouter();

    expect(
      await screen.findByTestId("sessions-empty")
    ).toBeInTheDocument();
  });

  it("renderer økter med lenker til /session/:id", async () => {
    mockSessions = [
      {
        session_id: "local-mini",
        label: "Local mini",
        ride_id: "123",
        mode: "outdoor",
        started_at: "2025-11-12T10:00:00Z",
      },
      {
        session_id: "bench-01",
        ride_id: "456",
        mode: "indoor",
        started_at: null,
      },
    ];

    renderWithRouter();

    const list = await screen.findByTestId("sessions-list");
    expect(list).toBeInTheDocument();

    const first = screen.getByText("Local mini");
    const link = first.closest("a");
    expect(link).toHaveAttribute("href", "/session/local-mini");
  });

  it("viser feilmelding ved error", () => {
    mockError = "Boom";
    renderWithRouter();

    expect(screen.getByTestId("sessions-error")).toHaveTextContent("Boom");
  });
});
