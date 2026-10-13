import { createContext, useContext, useSyncExternalStore, type ReactNode } from "react";

import type { SessionState, SessionStore } from "./session";

const SessionContext = createContext<SessionStore | null>(null);

export function SessionProvider({ store, children }: { store: SessionStore; children: ReactNode }) {
  return <SessionContext.Provider value={store}>{children}</SessionContext.Provider>;
}

export function useSessionStore(): SessionStore {
  const store = useContext(SessionContext);
  if (!store) throw new Error("useSessionStore must be used inside SessionProvider");
  return store;
}

export function useSession(): SessionState {
  const store = useSessionStore();
  return useSyncExternalStore(store.subscribe, store.getState);
}
