import type { components } from "./generated/auth";
import type { HttpClient } from "./http";
import type { Page, PageQuery } from "./common";

type Schemas = components["schemas"];
export type TokenPair = Schemas["TokenPair"];
export type User = Schemas["UserOut"];
export type Role = Schemas["Role"];
export type StaffCreate = Schemas["StaffCreate"];
export type UserUpdate = Schemas["UserUpdate"];

const BASE = "/api/v1/auth";

export function authApi(http: HttpClient) {
  return {
    login: (email: string, password: string) =>
      http.request<TokenPair>("POST", `${BASE}/login`, {
        json: { email, password },
        auth: false,
      }),
    refresh: (refreshToken: string) =>
      http.request<TokenPair>("POST", `${BASE}/refresh`, {
        json: { refresh_token: refreshToken },
        auth: false,
      }),
    logout: (refreshToken: string) =>
      http.request<undefined>("POST", `${BASE}/logout`, {
        json: { refresh_token: refreshToken },
        auth: false,
      }),
    me: () => http.request<User>("GET", `${BASE}/me`),
    listUsers: (query: PageQuery & { role?: Role | undefined }) =>
      http.request<Page<User>>("GET", `${BASE}/users`, { query: { ...query } }),
    createStaff: (data: StaffCreate) =>
      http.request<User>("POST", `${BASE}/users/staff`, { json: data }),
    updateUser: (id: string, changes: UserUpdate) =>
      http.request<User>("PATCH", `${BASE}/users/${id}`, { json: changes }),
  };
}

export type AuthApi = ReturnType<typeof authApi>;
