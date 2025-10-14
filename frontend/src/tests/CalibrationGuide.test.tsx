// frontend/src/tests/CalibrationGuide.test.tsx
import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import CalibrationGuide from "../components/CalibrationGuide";

describe("CalibrationGuide", () => {
  it("viser og lukker uten feil (Hopp over)", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onCalibrated = vi.fn();

    render(
      <CalibrationGuide
        sessionId="ABC"
        isOpen
        onClose={onClose}
        onCalibrated={onCalibrated}
        isMock
      />
    );

    // Tittel finnes
    expect(screen.getByText(/Kalibreringsveiledning/i)).toBeInTheDocument();

    // Klikk 'Hopp over' lukker
    await user.click(screen.getByRole("button", { name: /Hopp over/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onCalibrated).not.toHaveBeenCalled();
  });

  it("går gjennom steg og kaller onCalibrated ved 'Fullfør' (eller siste steg) i mock-modus", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onCalibrated = vi.fn();

    render(
      <CalibrationGuide
        sessionId="ABC"
        isOpen
        onClose={onClose}
        onCalibrated={onCalibrated}
        isMock
      />
    );

    // Knappetekster vi anser som 'fullfør'
    const finishRegex =
      /(Ferdig|Fullfør(?:\s+kalibrering)?|Fullfør\s+måling|Avslutt|Lagre)/i;

    // Inntil vi finner en 'fullfør'-handling:
    // - forsøk å klikke en 'fullfør'-knapp (flere varianter)
    // - ellers klikk 'Neste' hvis tilgjengelig
    // - hvis ingen finnes, bryt (kan bety at komponenten auto-fullførte og lukket)
    for (let i = 0; i < 20; i++) {
      // 1) Finn en tydelig 'fullfør'-knapp (role)
      const finishBtn = screen.queryByRole("button", { name: finishRegex });
      if (finishBtn) {
        await user.click(finishBtn);
        break;
      }

      // 2) Noen varianter kan ha tekstnode/link – prøv å finne tekst og klikk nærmeste knapp
      const finishText = screen.queryByText(finishRegex);
      if (finishText) {
        const maybeButton = finishText.closest("button");
        if (maybeButton) {
          await user.click(maybeButton);
          break;
        }
        // Hvis det ikke er en knapp, men f.eks. en <a>, prøv å klikke den direkte
        // (Testing Library vil kaste hvis den ikke er klikkbar)
        await user.click(finishText as HTMLElement);
        break;
      }

      // 3) Ellers klikk "Neste" hvis den finnes
      const nextBtn = screen.queryByRole("button", { name: /Neste/i });
      if (nextBtn) {
        await user.click(nextBtn);
        continue;
      }

      // 4) Ingenting å trykke på – bryt
      break;
    }

    // I mock-modus forventer vi at komponenten fullfører og kaller begge callbacks.
    await waitFor(() => {
      expect(onCalibrated).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  it("rendrer ikke når isOpen=false (HR-only forventet praksis)", () => {
    const onClose = vi.fn();
    const onCalibrated = vi.fn();

    render(
      <CalibrationGuide
        sessionId="ABC"
        isOpen={false}
        onClose={onClose}
        onCalibrated={onCalibrated}
        isMock
      />
    );

    // Ingenting rendres når modal er lukket
    expect(screen.queryByText(/Kalibreringsveiledning/i)).toBeNull();
  });
});
