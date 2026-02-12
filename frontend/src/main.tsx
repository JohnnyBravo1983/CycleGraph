// frontend/src/main.tsx

// FETCH INTERCEPTOR - redirect /api/* to backend
(function () {
  const BACKEND = "https://api.cyclegraph.app";
  const originalFetch = window.fetch;

  window.fetch = function (input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    if (typeof input === "string" && input.startsWith("/api/")) {
      console.log("[INTERCEPTOR] Redirect:", input, "→", BACKEND + input);
      input = BACKEND + input;
    }
    return originalFetch(input, init);
  };

  console.log("[INTERCEPTOR] Loaded from main.tsx");
})();

import "./devFetchShim";
import "./index.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";

import App from "./App";
import { installAxiosDevRewrite } from "./lib/axiosDevRewrite";

// ✅ Guards (Task 1.7)
import { AuthGateProvider } from "./auth/AuthGateProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { RequireOnboarding } from "./auth/RequireOnboarding";
import ProtectedLayout from "./auth/ProtectedLayout";

// Live + Demo entry pages
import Home from "./routes/Home"; // ✅ LIVE entry (dev)
import { LandingPage } from "./routes/LandingPage"; // ✅ DEMO/marketing entry (prod)

// Routes
import LoginPage from "./routes/LoginPage";
import SignupPage from "./routes/SignupPage";
import OnboardingPage from "./routes/OnboardingPage";
import ImportRidesPage from "./routes/ImportRidesPage";
import CalibrationPage from "./routes/CalibrationPage";
import DashboardPage from "./routes/DashboardPage";
import RidesPage from "./routes/RidesPage";
import TrendsPage from "./routes/TrendsPage";
import GoalsPage from "./routes/GoalsPage";
import ProfilePage from "./routes/ProfilePage";
import SessionView from "./routes/SessionView";

// How it works
import { HowItWorksPage } from "./routes/HowItWorksPage";

// ✅ Fix Android portrait "font boosting" / autosizing causing layout overflow
// Must run before first render.
(function () {
  try {
    const style = document.createElement("style");
    style.setAttribute("data-cg", "text-size-adjust-fix");
    style.textContent = `
      html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
      body { overflow-x: hidden; }
    `;
    document.head.appendChild(style);
    console.log("[main.tsx] Applied text-size-adjust fix");
  } catch (e) {
    console.warn("[main.tsx] Could not apply text-size-adjust fix", e);
  }
})();

// Installer dev-rewrite for axios FØR appen starter (kun i dev)
if (import.meta.env.DEV) {
  installAxiosDevRewrite();
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      // ✅ DEV: live Home (signup/login), PROD: demo Landing
      { index: true, element: import.meta.env.DEV ? <Home /> : <LandingPage /> },

      // ✅ PUBLIC
      { path: "login", element: <LoginPage /> },
      { path: "signup", element: <SignupPage /> },
      { path: "how-it-works", element: <HowItWorksPage /> },

      // ✅ AUTH REQUIRED, allow NOT-onboarded
      {
        path: "onboarding",
        element: (
          <RequireAuth>
            <RequireOnboarding allowUnonboarded>
              <OnboardingPage />
            </RequireOnboarding>
          </RequireAuth>
        ),
      },
      {
        path: "onboarding/import",
        element: (
          <RequireAuth>
            <RequireOnboarding allowUnonboarded>
              <ImportRidesPage />
            </RequireOnboarding>
          </RequireAuth>
        ),
      },

      // ✅ PROTECTED GROUP (auth + onboarded)
      {
        element: <ProtectedLayout />,
        children: [
          { path: "calibration", element: <CalibrationPage /> },
          { path: "dashboard", element: <DashboardPage /> },
          { path: "rides", element: <RidesPage /> },
          { path: "trends", element: <TrendsPage /> },
          { path: "goals", element: <GoalsPage /> },
          { path: "profile", element: <ProfilePage /> },
          { path: "session/:id", element: <SessionView /> },

          // leaderboards er protected også
          { path: "leaderboards", element: <Navigate to="/dashboard" replace /> },
        ],
      },

      // Fallback
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

console.log("[main.tsx] router loaded");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthGateProvider>
      <RouterProvider router={router} />
    </AuthGateProvider>
  </React.StrictMode>
);
