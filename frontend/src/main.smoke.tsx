import React from "react";
import ReactDOM from "react-dom/client";

const rootEl = document.getElementById("root");

if (!rootEl) {
  throw new Error("Fant ikke root-elementet");
}

const root = ReactDOM.createRoot(rootEl);

root.render(
  <React.StrictMode>
    <div
      style={{
        padding: "2rem",
        fontFamily: "system-ui, sans-serif",
        fontSize: "1.25rem",
      }}
    >
      <h1>CycleGraph – dev smoke test</h1>
      <p>Hvis du ser denne teksten, funker Vite-dev på port 5173 🎯</p>
    </div>
  </React.StrictMode>
);