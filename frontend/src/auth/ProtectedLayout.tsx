// frontend/src/auth/ProtectedLayout.tsx
import { Outlet } from "react-router-dom";
import { RequireAuth } from "./RequireAuth";
import { RequireOnboarding } from "./RequireOnboarding";

export default function ProtectedLayout() {
  return (
    <RequireAuth>
      <RequireOnboarding>
        <Outlet />
      </RequireOnboarding>
    </RequireAuth>
  );
}
