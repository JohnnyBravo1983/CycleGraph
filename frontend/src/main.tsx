// frontend/src/main.tsx
import "./index.css";
import "./devFetchShim";
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";

import App from "./App";
import SessionView from "./routes/SessionView";
import { installAxiosDevRewrite } from "./lib/axiosDevRewrite";
import { LandingPage } from "./routes/LandingPage";
import LoginPage from "./routes/LoginPage";
import SignupPage from "./routes/SignupPage";
import CalibrationPage from "./routes/CalibrationPage";
import DashboardPage from "./routes/DashboardPage";
import RidesPage from "./routes/RidesPage";
import TrendsPage from "./routes/TrendsPage";
import GoalsPage from "./routes/GoalsPage";
import ProfilePage from "./routes/ProfilePage";
import OnboardingPage from "./routes/OnboardingPage";
import { HowItWorksPage } from "./routes/HowItWorksPage";

// Installer dev-rewrite for axios FØR appen starter (kun i dev)
if (import.meta.env.DEV) {
  installAxiosDevRewrite();
}

/**
 * Routing rules:
 * - DEV: "/" -> /login  (live flow)
 * - PROD: "/" -> LandingPage (marketing + demo entry)
 * - LandingPage is always reachable at "/landing" (also in DEV).
 */
const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      // ✅ DEV starter på live login
      // ✅ PROD starter på landing
      {
        index: true,
        element: import.meta.env.DEV ? (
          <Navigate to="/login" replace />
        ) : (
          <LandingPage />
        ),
      },

      // ✅ Landing alltid tilgjengelig (også i dev)
      { path: "landing", element: <LandingPage /> },

      { path: "login", element: <LoginPage /> },
      { path: "signup", element: <SignupPage /> },

      { path: "onboarding", element: <OnboardingPage /> },

      { path: "calibration", element: <CalibrationPage /> },
      { path: "dashboard", element: <DashboardPage /> },

      { path: "rides", element: <RidesPage /> },
      { path: "trends", element: <TrendsPage /> },
      { path: "goals", element: <GoalsPage /> },
      { path: "profile", element: <ProfilePage /> },

      // How it works
      { path: "how-it-works", element: <HowItWorksPage /> },

      // Legacy truth-økt
      { path: "session/:id", element: <SessionView /> },

      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
