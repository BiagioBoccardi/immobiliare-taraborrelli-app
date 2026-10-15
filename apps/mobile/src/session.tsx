import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createApiClient,
  type ApiClient,
  type RegisterIn,
  type TokenPair,
  type User,
} from "@taraborrelli/api-client";
import * as SecureStore from "expo-secure-store";
import { createContext, useContext, useSyncExternalStore, type ReactNode } from "react";
import { Platform } from "react-native";

import { config } from "./config";

/** Where the refresh token is kept: the phone's keychain, or browser storage on the web preview. */
export interface TokenStorage {
  get(): Promise<string | null>;
  set(value: string): Promise<void>;
  remove(): Promise<void>;
}

const REFRESH_KEY = "taraborrelli.refresh";

export const deviceTokenStorage: TokenStorage =
  Platform.OS === "web"
    ? {
        get: () => AsyncStorage.getItem(REFRESH_KEY),
        set: (value) => AsyncStorage.setItem(REFRESH_KEY, value),
        remove: () => AsyncStorage.removeItem(REFRESH_KEY),
      }
    : {
        get: () => SecureStore.getItemAsync(REFRESH_KEY),
        set: (value) => SecureStore.setItemAsync(REFRESH_KEY, value),
        remove: () => SecureStore.deleteItemAsync(REFRESH_KEY),
      };

export type SessionStatus = "loading" | "anonymous" | "authenticated";

export interface SessionState {
  status: SessionStatus;
  user: User | null;
}

/**
 * Session of the app user. The access token lives only in memory; the refresh token is
 * stored on the device so the user stays logged in between launches.
 */
export class SessionStore {
  private accessToken: string | null = null;
  private state: SessionState = { status: "loading", user: null };
  private readonly listeners = new Set<() => void>();
  private api: ApiClient | null = null;

  constructor(private readonly storage: TokenStorage) {}

  attach(api: ApiClient): void {
    this.api = api;
  }

  getState = (): SessionState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getAccessToken = (): string | null => this.accessToken;

  refreshAccessToken = async (): Promise<string | null> => {
    const refreshToken = await this.storage.get().catch(() => null);
    if (!refreshToken || !this.api) return null;
    try {
      await this.saveTokens(await this.api.auth.refresh(refreshToken));
      return this.accessToken;
    } catch {
      return null;
    }
  };

  onSessionExpired = (): void => {
    void this.clear();
  };

  async restore(): Promise<void> {
    if (!(await this.refreshAccessToken())) {
      await this.clear();
      return;
    }
    try {
      await this.loadUser();
    } catch {
      await this.clear();
    }
  }

  async login(email: string, password: string): Promise<void> {
    await this.saveTokens(await this.requireApi().auth.login(email, password));
    await this.loadUser();
  }

  async register(data: RegisterIn): Promise<void> {
    await this.saveTokens(await this.requireApi().auth.register(data));
    await this.loadUser();
  }

  async logout(): Promise<void> {
    const refreshToken = await this.storage.get().catch(() => null);
    await this.clear();
    if (refreshToken && this.api) await this.api.auth.logout(refreshToken).catch(() => undefined);
  }

  /** GDPR erasure: the account and the requests linked to it are deleted. */
  async deleteAccount(): Promise<void> {
    await this.requireApi().auth.deleteMe();
    await this.clear();
  }

  private requireApi(): ApiClient {
    if (!this.api) throw new Error("API client not attached");
    return this.api;
  }

  private async loadUser(): Promise<void> {
    const user = await this.requireApi().auth.me();
    this.setState({ status: "authenticated", user });
  }

  private async saveTokens(tokens: TokenPair): Promise<void> {
    this.accessToken = tokens.access_token;
    await this.storage.set(tokens.refresh_token);
  }

  private async clear(): Promise<void> {
    this.accessToken = null;
    await this.storage.remove().catch(() => undefined);
    this.setState({ status: "anonymous", user: null });
  }

  private setState(next: SessionState): void {
    this.state = next;
    for (const listener of this.listeners) listener();
  }
}

/** Builds the API client wired to a session, so expired tokens are renewed transparently. */
export function createSession(storage: TokenStorage = deviceTokenStorage): {
  session: SessionStore;
  api: ApiClient;
} {
  const session = new SessionStore(storage);
  const api = createApiClient({
    baseUrl: config.apiBaseUrl,
    auth: {
      getAccessToken: session.getAccessToken,
      refreshAccessToken: session.refreshAccessToken,
      onSessionExpired: session.onSessionExpired,
    },
  });
  session.attach(api);
  return { session, api };
}

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
  return useSyncExternalStore(store.subscribe, store.getState, store.getState);
}
