// frontend/src/tests/SessionView.test.tsx
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen, fireEvent } from '@testing-library/react';
import type { SessionReport } from '../types/session';

// Stub SessionCard for å unngå komplekse props/render
vi.mock('../components/SessionCard', () => ({
  default: () => <div data-testid="session-card">SessionCard</div>,
}));

// Dynamisk mock av store: vi kan sette state pr test
const fetchSessionMock = vi.fn();

type Source = 'api' | 'mock' | null;
type StoreSlice = {
  session: SessionReport | null;
  loading: boolean;
  error: string | null;
  source: Source;
  fetchSession: (id?: string) => Promise<void>;
};

let mockedState: StoreSlice = {
  session: null,
  loading: false,
  error: 'HTTP 404 Not Found',
  source: 'api',
  fetchSession: fetchSessionMock,
};

vi.mock('../state/sessionStore', () => ({
  useSessionStore: () => mockedState,
}));

// ✅ Riktig sti fra src/tests → src/routes
import SessionView from '../routes/SessionView';

describe('SessionView', () => {
  beforeEach(() => {
    fetchSessionMock.mockReset();
    mockedState = {
      session: null,
      loading: false,
      error: 'HTTP 404 Not Found',
      source: 'api',
      fetchSession: fetchSessionMock,
    };
  });

  function renderAt(path = '/session/ABC123') {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/session/:id" element={<SessionView />} />
        </Routes>
      </MemoryRouter>
    );
  }

  it('viser ErrorBanner med 404-tekst og lar oss retrye', () => {
    renderAt('/session/ABC123');

    expect(
      screen.getByText(/Ingen data å vise for denne økten/i)
    ).toBeInTheDocument();

    const retry = screen.getByRole('button', { name: /prøv igjen/i });
    fireEvent.click(retry);
    expect(fetchSessionMock).toHaveBeenCalledWith('ABC123');
  });

  it('viser SessionCard når session finnes', () => {
    mockedState.session = { schema_version: '1.0.0' } as unknown as SessionReport;
    mockedState.error = null;

    renderAt('/session/ABC123');
    expect(screen.getByTestId('session-card')).toBeInTheDocument();
  });
});
