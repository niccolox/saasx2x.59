// The page has one origin in each mode, so the code calls `/api/dashboard` with no host and
// the server needs no CORS rule.
//   development: Vite serves the page on 127.0.0.1:5173 and sends /api to `saasx2x web`.
//   production:  `saasx2x web` serves web/dist and /api from one process.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:55441" },
  },
  build: { outDir: "dist", emptyOutDir: true },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test-setup.ts"],
  },
});
