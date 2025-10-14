// frontend/vite.config.ts
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const useMock = env.VITE_USE_MOCK === "true";
  const backend = env.VITE_BACKEND_URL || "http://localhost:8000";

  return {
    plugins: [
      react(),

      // Mock-API KUN når VITE_USE_MOCK=true
      {
        name: "mock-api",
        apply: "serve",
        configureServer(server) {
          if (!useMock) return;

          const now = Date.now();

          // Sanity: bør alltid svare 200
          server.middlewares.use("/api/ping", (_req, res) => {
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ ok: true, ts: now }));
          });

          // /api/trends -> ARRAY med { id, timestamp, np, pw, source, calibrated }
          server.middlewares.use("/api/trends", (_req, res) => {
            const rows = Array.from({ length: 30 }).map((_, i) => {
              const ts = now - (30 - i) * 2 * 24 * 3600 * 1000; // annenhver dag
              const hasPower = i % 7 !== 3; // noen HR-only punkter
              const np = hasPower ? Math.round(220 + Math.sin(i / 2) * 20 + (i % 5) * 2) : null;
              const pw = hasPower ? Math.round(210 + Math.cos(i / 3) * 18 + (i % 3) * 3) : null;

              return {
                id: `mock-${i}`,
                timestamp: ts, // ms epoch
                np,            // number | null
                pw,            // number | null
                source: "Mock",
                calibrated: i % 4 !== 0,
              };
            });

            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify(rows)); // ARRAY
          });

          // /api/sessions/summary -> ARRAY i samme form (fallback i TrendsChart)
          server.middlewares.use("/api/sessions/summary", (_req, res) => {
            const rows = Array.from({ length: 10 }).map((_, i) => {
              const ts = now - (10 - i) * 7 * 24 * 3600 * 1000; // ukentlig bakover
              const hasPower = i % 5 !== 2;
              const np = hasPower ? Math.round(200 + i * 3) : null;
              const pw = hasPower ? Math.round(195 + i * 2) : null;

              return {
                id: `sum-${i}`,
                timestamp: ts,
                np,
                pw,
                source: "Mock",
                calibrated: i % 3 === 0,
              };
            });

            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify(rows)); // ARRAY
          });
        },
      },
    ],

    server: {
      // Når mock er AV → proxy til backend (løser CORS og base-URL)
      proxy: useMock
        ? undefined
        : {
            "/api": {
              target: backend,
              changeOrigin: true,
            },
          },
    },
  };
});
