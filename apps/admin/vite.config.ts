import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// In development the API is reached through the gateway (docker compose, port 8000).
// With VITE_LOCAL_SERVICES=1 (scripts/dev-local.sh) each service is reached directly instead.
const LOCAL_SERVICES = {
  "/api/v1/auth": "http://localhost:8001",
  "/api/v1/lead": "http://localhost:8002",
  "/api/v1/property": "http://localhost:8003",
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const gateway = env.VITE_PROXY_TARGET || "http://localhost:8000";
  return {
    plugins: [react()],
    define: {
      __API_BASE_URL__: JSON.stringify(env.VITE_API_BASE_URL ?? ""),
    },
    server: {
      port: 5173,
      proxy: env.VITE_LOCAL_SERVICES === "1" ? LOCAL_SERVICES : { "/api": gateway },
    },
  };
});
