import { createApiClient } from "@taraborrelli/api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { ApiProvider } from "./api/ApiContext";
import { App } from "./App";
import { SessionProvider } from "./auth/SessionContext";
import { SessionStore } from "./auth/session";
import { config } from "./config";
import { applyTheme } from "./theme/applyTheme";
import "./theme/styles.css";

applyTheme();

const session = new SessionStore(window.sessionStorage);
const api = createApiClient({
  baseUrl: config.apiBaseUrl,
  auth: {
    getAccessToken: session.getAccessToken,
    refreshAccessToken: session.refreshAccessToken,
    onSessionExpired: session.onSessionExpired,
  },
});
session.attach(api);
void session.restore();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: true },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <ApiProvider api={api}>
      <SessionProvider store={session}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </SessionProvider>
    </ApiProvider>
  </StrictMode>,
);
