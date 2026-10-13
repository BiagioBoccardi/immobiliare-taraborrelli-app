import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// In development the API is reached through the gateway (docker compose, port 8000).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  return {
    plugins: [react()],
    define: {
      __API_BASE_URL__: JSON.stringify(env.VITE_API_BASE_URL ?? ""),
    },
    server: {
      port: 5173,
      proxy: {
        "/api": env.VITE_PROXY_TARGET || "http://localhost:8000",
      },
    },
  };
});
