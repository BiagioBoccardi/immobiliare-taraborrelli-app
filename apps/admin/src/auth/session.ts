import type { ApiClient, TokenPair, User } from "@taraborrelli/api-client";

/**
 * Session state outside React, so the API client can read and renew tokens.
 *
 * The access token lives only in memory. The refresh token is kept in sessionStorage:
 * it survives a page reload but not closing the browser, which limits the exposure of
 * a shared office computer.
 */

const REFRESH_KEY = "taraborrelli.admin.refresh";

export type SessionStatus = "loading" | "anonymous" | "authenticated";

export interface SessionState {
  status: SessionStatus;
  user: User | null;
  /** Set when the last login was refused for a reason the login page should show. */
  error: string | null;
}

const STAFF_ROLES = new Set(["staff", "admin"]);

export class SessionStore {
  private accessToken: string | null = null;
  private state: SessionState = { status: "loading", user: null, error: null };
  private readonly listeners = new Set<() => void>();
  private api: ApiClient | null = null;

  constructor(private readonly storage: Storage) {}

  /** The client is attached after creation because it needs this store's hooks. */
  attach(api: ApiClient): void {
    this.api = api;
  }

  getState = (): SessionState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getAccessToken = (): string | null => this.accessToken;

  /** Used by the API client on 401: rotates the refresh token and returns a new access token. */
  refreshAccessToken = async (): Promise<string | null> => {
    const refreshToken = this.storage.getItem(REFRESH_KEY);
    if (!refreshToken || !this.api) return null;
    try {
      this.saveTokens(await this.api.auth.refresh(refreshToken));
      return this.accessToken;
    } catch {
      return null;
    }
  };

  onSessionExpired = (): void => {
    this.clearTokens();
    this.setState({ status: "anonymous", user: null, error: "unauthorized" });
  };

  /** Restores the session after a page reload, if a refresh token is stored. */
  async restore(): Promise<void> {
    if (!(await this.refreshAccessToken())) {
      this.clearTokens();
      this.setState({ status: "anonymous", user: null, error: null });
      return;
    }
    await this.loadUser();
  }

  async login(email: string, password: string): Promise<void> {
    if (!this.api) throw new Error("API client not attached");
    this.saveTokens(await this.api.auth.login(email, password));
    await this.loadUser();
  }

  async logout(): Promise<void> {
    const refreshToken = this.storage.getItem(REFRESH_KEY);
    this.clearTokens();
    this.setState({ status: "anonymous", user: null, error: null });
    if (refreshToken && this.api) {
      await this.api.auth.logout(refreshToken).catch(() => undefined);
    }
  }

  private async loadUser(): Promise<void> {
    if (!this.api) throw new Error("API client not attached");
    const user = await this.api.auth.me();
    if (!STAFF_ROLES.has(user.role)) {
      // App users have valid accounts but no access to the admin panel.
      await this.logout();
      this.setState({ status: "anonymous", user: null, error: "not_staff" });
      return;
    }
    this.setState({ status: "authenticated", user, error: null });
  }

  private saveTokens(tokens: TokenPair): void {
    this.accessToken = tokens.access_token;
    this.storage.setItem(REFRESH_KEY, tokens.refresh_token);
  }

  private clearTokens(): void {
    this.accessToken = null;
    this.storage.removeItem(REFRESH_KEY);
  }

  private setState(next: SessionState): void {
    this.state = next;
    for (const listener of this.listeners) listener();
  }
}
