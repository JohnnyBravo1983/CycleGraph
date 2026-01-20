// frontend/src/auth/RequireOnboarding.tsx
import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthGate } from "./AuthGateProvider";

type Props = {
  children: ReactNode;
  allowUnonboarded?: boolean; // true for onboarding routes
};

export function RequireOnboarding({ children, allowUnonboarded }: Props) {
  const gate = useAuthGate();
  const path = window.location.pathname;

  console.log("[RequireOnboarding]", path, gate.status, gate.isOnboarded);

  if (gate.status === "checking") {
    return <div className="p-4">Loading…</div>;
  }

  if (gate.status === "guest") {
    return <Navigate to="/login" replace />;
  }

  // ✅ Tillat uonboarded brukere på:
  // - /onboarding
  // - /onboarding/import
  const isOnboardingFlow =
    path === "/onboarding" || path.startsWith("/onboarding/");

  if (!gate.isOnboarded && !allowUnonboarded && !isOnboardingFlow) {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
}
