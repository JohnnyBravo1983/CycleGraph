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

// Installer dev-rewrite for axios FØR appen starter (kun i dev)
if (import.meta.env.DEV) {
  installAxiosDevRewrite();
}

/**
 * Router (Fase 1 – skeleton):
 *  - "/"            -> LandingPage (ny inngang)
 *  - "/session/:id" -> SessionView (legacy element of truth)
 *  - "*"(catch-all) -> "/"
 *
 * Senere:
 *  - "/login", "/signup", "/dashboard", "/rides", osv. legges til
 *    i henhold til ROUTES_PLAN.md
 */
const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
children: [
  { index: true, element: <LandingPage /> },

  { path: "login", element: <LoginPage /> },
  { path: "signup", element: <SignupPage /> },
  { path: "calibration", element: <CalibrationPage /> },
  { path: "dashboard", element: <DashboardPage /> },

  { path: "rides", element: <RidesPage /> },
  { path: "trends", element: <TrendsPage /> },
  { path: "goals", element: <GoalsPage /> },
  { path: "profile", element: <ProfilePage /> },

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