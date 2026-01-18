// frontend/src/auth/RequireOnboarding.tsx
import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthGate } from "./AuthGateProvider";

type Props = {
  children: ReactNode;
  allowUnonboarded?: boolean; // true ONLY for /onboarding route
};

export function RequireOnboarding({ children, allowUnonboarded }: Props) {
  const gate = useAuthGate();
  console.log("[RequireOnboarding]", window.location.pathname, gate.status, gate.isOnboarded);
  if (gate.status === "checking") {
    return <div className="p-4">Loading…</div>;
  }

  if (gate.status === "guest") {
    return <Navigate to="/login" replace />;
  }

  if (!allowUnonboarded && !gate.isOnboarded) {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
}
