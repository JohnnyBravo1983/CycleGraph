// frontend/src/auth/RequireAuth.tsx
import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthGate } from "./AuthGateProvider";

export function RequireAuth({ children }: { children: ReactNode }) {
  const gate = useAuthGate();
  const loc = useLocation();

  if (gate.status === "checking") {
    return <div className="p-4">Loading…</div>;
  }

  if (gate.status === "guest") {
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  }

  return <>{children}</>;
}
