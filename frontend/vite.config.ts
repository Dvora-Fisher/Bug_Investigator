import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL(".", import.meta.url));

// The API runs on :8000 (uvicorn). Proxying /api keeps the browser on one origin, so server-sent
// events and uploads need no CORS setup. Set API_TARGET (e.g. in frontend/.env.local) to use another port.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ROOT, "");
  return {
    root: ROOT,
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: false,
      proxy: { "/api": { target: env.API_TARGET || "http://127.0.0.1:8000", changeOrigin: true } },
    },
  };
});
