import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// import tailwind from "@tailwindcss/vite"; // Aktiver hvis du vil bruke Tailwind plugin i tillegg

export default defineConfig({
  plugins: [
    react(),
    // tailwind(), // ← fjern kommentaren hvis du vil bruke plugin
  ],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000", // ← endre hvis backend kjører annet sted
        changeOrigin: true,
      },
    },
  },
});
