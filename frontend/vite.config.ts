import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/chat": backend,
      "/voice": backend,
      "/report": backend,
      "/navigate": backend,
      "/places": backend,
      "/preferences": backend,
      "/vehicle": { target: backend, ws: true },
    },
  },
});
