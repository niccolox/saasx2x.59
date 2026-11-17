import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Development: `uv run saasx2x web` on :55441 and `npm run dev` on :5173.
// The proxy sends /api to the Python process. Production has no proxy: FastAPI serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    // changeOrigin sets Host to 127.0.0.1:55441, which the Python host allow-list accepts.
    proxy: { "/api": { target: "http://127.0.0.1:55441", changeOrigin: true } },
  },
  build: { outDir: "dist", sourcemap: false },
  test: { environment: "jsdom", include: ["src/**/*.test.{ts,tsx}"] },
});
