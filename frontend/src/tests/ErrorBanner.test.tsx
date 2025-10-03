// frontend/tests/ErrorBanner.test.tsx
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ErrorBanner from "../components/ErrorBanner"; // ← riktig sti fra src/tests → src/components


describe("ErrorBanner", () => {
  it("viser melding og kaller onRetry ved klikk", () => {
    const onRetry = vi.fn();
    render(<ErrorBanner message="Kunne ikke hente data." onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Kunne ikke hente data/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /prøv igjen/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});