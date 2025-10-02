/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    test: {
        globals: true, // <- gjør describe/it/expect globale
        environment: "jsdom", // jsdom passer fint i React-prosjekt
        include: ["src/**/*.{test,spec}.{ts,tsx}"]
    }
});
