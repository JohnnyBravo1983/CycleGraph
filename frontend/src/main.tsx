// frontend/src/main.tsx
import "./index.css";
import "./devFetchShim";
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";

import App from "./App";
import { installAxiosDevRewrite } from "./lib/axiosDevRewrite";

// Live + Demo entry pages
import Home from "./routes/Home"; // ✅ LIVE entry (dev)
import { LandingPage } from "./routes/LandingPage"; // ✅ DEMO/marketing entry (prod)

// Routes
import LoginPage from "./routes/LoginPage";
import SignupPage from "./routes/SignupPage";
import OnboardingPage from "./routes/OnboardingPage";
import CalibrationPage from "./routes/CalibrationPage";
import DashboardPage from "./routes/DashboardPage";
import RidesPage from "./routes/RidesPage";
import TrendsPage from "./routes/TrendsPage";
import GoalsPage from "./routes/GoalsPage";
import ProfilePage from "./routes/ProfilePage";
import SessionView from "./routes/SessionView";

// How it works
import { HowItWorksPage } from "./routes/HowItWorksPage";

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

      // Auth / onboarding
      { path: "login", element: <LoginPage /> },
      { path: "signup", element: <SignupPage /> },
      { path: "onboarding", element: <OnboardingPage /> },

      // App pages
      { path: "calibration", element: <CalibrationPage /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "rides", element: <RidesPage /> },
      { path: "trends", element: <TrendsPage /> },
      { path: "goals", element: <GoalsPage /> },
      { path: "profile", element: <ProfilePage /> },

      // Info
      { path: "how-it-works", element: <HowItWorksPage /> },

      // Legacy truth-økt
      { path: "session/:id", element: <SessionView /> },

      // ✅ Safety: header has /leaderboards link, but we don't have a route component here
      { path: "leaderboards", element: <Navigate to="/dashboard" replace /> },

      // Fallback
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
