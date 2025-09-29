// frontend/src/main.tsx
import "./index.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";

import App from "./App";
import SessionView from "./routes/SessionView";

/**
 * Router:
 *  - "/"            -> /session/mock
 *  - "/session"     -> /session/mock
 *  - "/session/:id" -> SessionView (mock/live styres av .env + id)
 *  - "*"(catch-all) -> /session/mock
 */
const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/session/mock" replace /> },
      { path: "session", element: <Navigate to="/session/mock" replace /> },
      { path: "session/:id", element: <SessionView /> },
      { path: "*", element: <Navigate to="/session/mock" replace /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);