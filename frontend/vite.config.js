import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard backend (FastAPI) serves the built SPA from src/tsabot/dashboard/web.
// During development run this dev server and proxy /api to the backend on :8788.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/tsabot/dashboard/web",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8788",
    },
  },
});
