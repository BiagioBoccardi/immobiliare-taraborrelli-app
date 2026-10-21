/** Minimal HTTP layer shared by every service client. */

export interface ApiErrorBody {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

/** Error with the backend's uniform format: {"code", "message", "details"}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
  }
}

export interface AuthHooks {
  /** Current access token, if any. */
  getAccessToken: () => string | null;
  /** Gets a new access token (e.g. with the refresh token). Returns null if not possible. */
  refreshAccessToken: () => Promise<string | null>;
  /** Called when the session cannot be renewed: the user must log in again. */
  onSessionExpired: () => void;
}

export interface ClientOptions {
  /** Gateway origin, e.g. "https://api.example.com". Empty string for same origin. */
  baseUrl: string;
  auth?: AuthHooks;
  fetch?: typeof fetch;
}

export type QueryValue =
  string | number | boolean | null | undefined | readonly (string | number)[];
export type Query = Record<string, QueryValue>;

export interface RequestOptions {
  query?: Query | undefined;
  json?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
  /** Whether to send the access token. Public endpoints set this to false. */
  auth?: boolean;
}

/** Builds a query string by hand: React Native's URLSearchParams is incomplete. */
export function buildQuery(query: Query | undefined): string {
  if (!query) return "";
  const parts: string[] = [];
  const add = (key: string, value: string | number | boolean) =>
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) add(key, item);
    } else {
      add(key, value as string | number | boolean);
    }
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { code?: unknown }).code === "string" &&
    typeof (value as { message?: unknown }).message === "string"
  );
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly auth: AuthHooks | undefined;
  private readonly fetchImpl: typeof fetch;
  private refreshing: Promise<string | null> | null = null;

  constructor(options: ClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.auth = options.auth;
    this.fetchImpl = options.fetch ?? ((input, init) => fetch(input, init));
  }

  async request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    return this.parse<T>(await this.sendWithRefresh(method, path, options));
  }

  /** For file downloads (e.g. an Excel template): the body as a Blob. */
  async requestBlob(method: string, path: string, options: RequestOptions = {}): Promise<Blob> {
    const response = await this.sendWithRefresh(method, path, options);
    if (!response.ok) return this.parse<never>(response); // throws ApiError
    return response.blob();
  }

  private async sendWithRefresh(
    method: string,
    path: string,
    options: RequestOptions,
  ): Promise<Response> {
    const useAuth = options.auth ?? true;
    let response = await this.send(method, path, options, useAuth);
    if (response.status === 401 && useAuth && this.auth) {
      const token = await this.refreshOnce();
      if (token === null) {
        this.auth.onSessionExpired();
      } else {
        response = await this.send(method, path, options, useAuth);
        if (response.status === 401) this.auth.onSessionExpired();
      }
    }
    return response;
  }

  /** Concurrent 401s share a single refresh, so a rotated refresh token is used only once. */
  private refreshOnce(): Promise<string | null> {
    if (!this.auth) return Promise.resolve(null);
    if (!this.refreshing) {
      this.refreshing = this.auth
        .refreshAccessToken()
        .catch(() => null)
        .finally(() => {
          this.refreshing = null;
        });
    }
    return this.refreshing;
  }

  private async send(
    method: string,
    path: string,
    options: RequestOptions,
    useAuth: boolean,
  ): Promise<Response> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...options.headers,
    };
    let body: BodyInit | undefined;
    if (options.form) {
      body = options.form; // the browser sets the multipart boundary
    } else if (options.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.json);
    }
    const token = useAuth ? this.auth?.getAccessToken() : null;
    if (token) headers.Authorization = `Bearer ${token}`;
    try {
      return await this.fetchImpl(`${this.baseUrl}${path}${buildQuery(options.query)}`, {
        method,
        headers,
        body,
      });
    } catch {
      throw new ApiError(0, {
        code: "network_error",
        message: "Network error",
        details: {},
      });
    }
  }

  private async parse<T>(response: Response): Promise<T> {
    if (response.status === 204) return undefined as T;
    const text = await response.text();
    let data: unknown = undefined;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    if (!response.ok) {
      throw new ApiError(
        response.status,
        isErrorBody(data)
          ? { ...data, details: data.details ?? {} }
          : {
              code: "http_error",
              message: `HTTP ${response.status}`,
              details: {},
            },
      );
    }
    return data as T;
  }
}
