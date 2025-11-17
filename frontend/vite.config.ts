import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

// Minimal trygg config for app-frontend
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true, // feiler heller enn å hoppe til 5174/5175/5176
  },
  // Viktig: vi setter IKKE root/appType/custom greier her.
  // Da vil Vite bruke mappa med vite.config som root,
  // og index.html i frontend/ blir entry.
});