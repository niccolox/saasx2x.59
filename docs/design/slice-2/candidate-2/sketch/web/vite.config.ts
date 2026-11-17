// Development: run `uv run saasx2x web` (port 55441) and `npm run dev` (port 5173).
// Vite serves the page with hot reload and sends /api to the Python process.
// Production: `npm run build` writes dist/, and `saasx2x web` serves it. No Node at run time.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:55441" },
  },
  build: { outDir: "dist", assetsDir: "assets", sourcemap: true },
  test: { environment: "jsdom" },
});
