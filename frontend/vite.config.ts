// frontend/vite.config.ts
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "");
  const useMock = env.VITE_USE_MOCK === "true";
  const backend = (env.VITE_BACKEND_URL || "http://127.0.0.1:5175").replace(
    "localhost",
    "127.0.0.1"
  );

  console.log(`[vite] mode=${mode} useMock=${useMock} backend=${backend}`);

  return {
    plugins: [
      react(),

      // Mock-API KUN når VITE_USE_MOCK=true (dev server)
      {
        name: "mock-api",
        apply: "serve",
        configureServer(server) {
          if (!useMock) return;

          const now = Date.now();

          server.middlewares.use("/api/ping", (_req, res) => {
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ ok: true, ts: now }));
          });

          server.middlewares.use("/api/trends", (_req, res) => {
            const rows = Array.from({ length: 30 }).map((_, i) => {
              const ts = now - (30 - i) * 2 * 24 * 3600 * 1000;
              const hasPower = i % 7 !== 3;
              const np = hasPower
                ? Math.round(220 + Math.sin(i / 2) * 20 + (i % 5) * 2)
                : null;
              const pw = hasPower
                ? Math.round(210 + Math.cos(i / 3) * 18 + (i % 3) * 3)
                : null;
              return {
                id: `mock-${i}`,
                timestamp: ts,
                np,
                pw,
                source: "Mock",
                calibrated: i % 4 !== 0,
              };
            });
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify(rows));
          });

          server.middlewares.use("/api/sessions/summary", (_req, res) => {
            const rows = Array.from({ length: 10 }).map((_, i) => {
              const ts = now - (10 - i) * 7 * 24 * 3600 * 1000;
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
            res.end(JSON.stringify(rows));
          });
        },
      },
    ],

    // Proxy til backend når mock er AV
    server: useMock
      ? {}
      : {
          proxy: {
            "/api": {
              target: backend,
              changeOrigin: true,
              secure: false,
              cookieDomainRewrite: "localhost",
            },
            "/status": {
              target: backend,
              changeOrigin: true,
              secure: false,
              cookieDomainRewrite: "localhost",
            },
          },
        },

    // --- ytelsesboost for prod-build ---
    build: {
      sourcemap: false,
      target: "esnext",
      cssCodeSplit: true,
      minify: "esbuild",
    },

    // Dropp støy i prod (bedre Lighthouse)
    esbuild: mode === "production" ? { drop: ["console", "debugger"] } : {},

    // (valgfritt) compile-time-konstanter
    define: {
      __USE_MOCK__: JSON.stringify(useMock),
      __BACKEND_URL__: JSON.stringify(backend),
    },

    // Vitest (lå inne i samme config – IKKE egen export default)
    test: {
      globals: true,
      environment: "jsdom",
      include: ["src/**/*.{test,spec}.{ts,tsx}"],
    },
  };
});
