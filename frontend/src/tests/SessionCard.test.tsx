// src/tests/SessionCard.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SessionCard from '../components/SessionCard';

// 1) Hent props-typen direkte fra komponenten og utvid med felter vi tester
type CardProps = React.ComponentProps<typeof SessionCard>;
type CardSessionBase = CardProps['session'];
type CardSession = CardSessionBase & {
  reason?: string | null;
  calibration_reason?: string | null;
};

// 2) Bygg en sesjon som matcher SessionCard-kravene
function makeSession(partial: Partial<CardSession> = {}): CardSession {
  const base = {
    schema_version: '0.0.0',
    calibrated: true,
    status: 'FULL',
    mode: 'outdoor',

    // Komponent forventer number[] | null
    watts: Array.from({ length: 40 }, (_, i) => 200 + i),

    // nøkkelmetrikker brukt i kortet
    np: 250,
    if_: 0.85,
    vi: 1.06,
    pa_hr: 4.2,
    w_per_beat: 1.45,
    cgs: 76.2,
    precision_watt_value: 262,

    // bunnotis
    sources: ['test'],

    // trinn 6-felter
    publish_state: 'done',
    publish_time: '2025-10-22T08:00:00.000Z',
    CdA: 0.29,
    crr_used: 0.0035,
    rider_weight: 93,
    bike_weight: 8.4,
    tire_width: 28,
    bike_type: 'road',
  } as unknown as CardSession;

  return { ...base, ...partial } as CardSession;
}

describe('SessionCard (Trinn 6)', () => {
  it('viser publiseringsstatus som grønn ✓ når state=done', () => {
    const s = makeSession({ publish_state: 'done' });
    render(<SessionCard session={s} />);
    const pill = screen.getByTestId('publish-pill');
    expect(pill.textContent).toContain('✓');
    expect(pill.textContent?.toLowerCase()).toContain('published');
  });

  it('viser rød advarsel ved failed publish', () => {
    const s = makeSession({ publish_state: 'failed' });
    render(<SessionCard session={s} />);
    const pill = screen.getByTestId('publish-pill');
    expect(pill.textContent?.toLowerCase()).toContain('failed');
  });

  it('viser “Rulleøkt – ikke kalibrert” når reason=indoor_session og ikke kalibrert', () => {
    const s = makeSession({
      reason: 'indoor_session',
      calibrated: false,
      calibration_reason: 'indoor_session',
    });
    render(<SessionCard session={s} />);
    expect(screen.getByText(/Rulleøkt – ikke kalibrert/i)).toBeInTheDocument();
  });

  it('viser PW CI-seksjon selv uten CI-verdier (robust fallback)', () => {
    const s = makeSession({
      // bruk null i stedet for undefined for å trigge fallback uten TS-støy
      precision_watt_value: null,
    });
    render(<SessionCard session={s} />);
    expect(screen.getByText('PW CI')).toBeInTheDocument();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('renderer CdA og Crr med riktige desimaler', () => {
    const s = makeSession({ CdA: 0.29123, crr_used: 0.003456 });
    render(<SessionCard session={s} />);
    expect(screen.getByText(/0\.291 m²/)).toBeInTheDocument();
    expect(screen.getByText(/0\.0035/)).toBeInTheDocument();
  });
});
