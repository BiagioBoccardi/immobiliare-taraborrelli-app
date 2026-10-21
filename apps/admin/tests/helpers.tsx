import type { AdminProperty, ApiClient, Lead, Page, User } from "@taraborrelli/api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ApiProvider } from "../src/api/ApiContext";
import { App } from "../src/App";
import { SessionProvider } from "../src/auth/SessionContext";
import { SessionStore } from "../src/auth/session";

type Mocked<T> = { [K in keyof T]: jest.Mock };
export type FakeApi = { [G in keyof ApiClient]: Mocked<ApiClient[G]> };

export function page<T>(items: T[], total = items.length): Page<T> {
  return { items, total, page: 1, size: 20 };
}

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "user-1",
    email: "laura@example.com",
    full_name: "Laura Agente",
    role: "staff",
    is_active: true,
    created_at: "2026-10-01T09:00:00Z",
    last_login_at: null,
    ...overrides,
  };
}

export function makeLead(overrides: Partial<Lead> = {}): Lead {
  return {
    id: "lead-1",
    kind: "valuation",
    status: "new",
    priority: "high",
    intention: "decided",
    full_name: "Mario Rossi",
    phone: "3330000000",
    email: null,
    municipality: "Chieti",
    property_type: "apartment",
    surface_sqm: 95,
    rooms: 4,
    condition: "good",
    details: {},
    message: null,
    marketing_consent: false,
    privacy_policy_version: "2026-01",
    contact_consent_at: "2026-10-12T09:00:00Z",
    next_contact_at: null,
    staff_notes: null,
    created_at: "2026-10-12T09:00:00Z",
    updated_at: "2026-10-12T09:00:00Z",
    ...overrides,
  };
}

export function makeProperty(overrides: Partial<AdminProperty> = {}): AdminProperty {
  return {
    id: "prop-1",
    reference: "TR00001",
    external_ref: null,
    status: "draft",
    contract: "sale",
    property_type: "apartment",
    title: "Trilocale luminoso",
    description: "",
    price: 120000,
    condominium_fees: null,
    surface_sqm: 95,
    rooms: 3,
    bedrooms: 2,
    bathrooms: 1,
    floor: null,
    total_floors: null,
    year_built: null,
    condition: null,
    energy_class: null,
    features: [],
    is_featured: false,
    municipality: "Chieti",
    zone: null,
    address: "Via di Prova 1",
    latitude: null,
    longitude: null,
    show_exact_location: false,
    tenant_types: [],
    accommodation: null,
    available_from: null,
    published_at: null,
    closed_at: null,
    created_at: "2026-10-12T09:00:00Z",
    updated_at: "2026-10-12T09:00:00Z",
    photos: [],
    ...overrides,
  };
}

/** API with every method mocked; tests configure only what they use. */
export function fakeApi(): FakeApi {
  const group = (names: string[]) =>
    Object.fromEntries(names.map((name) => [name, jest.fn()])) as Record<string, jest.Mock>;
  return {
    auth: group(["login", "refresh", "logout", "me", "listUsers", "createStaff", "updateUser"]),
    lead: group([
      "createValuation",
      "completeValuation",
      "createOwnerRequest",
      "listLeads",
      "getLead",
      "updateLead",
      "deleteLead",
    ]),
    property: group([
      "search",
      "getPublic",
      "listSold",
      "list",
      "get",
      "create",
      "update",
      "changeStatus",
      "remove",
      "uploadPhoto",
      "updatePhoto",
      "reorderPhotos",
      "deletePhoto",
      "previewImport",
      "runImport",
      "importTemplate",
    ]),
  } as unknown as FakeApi;
}

export function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => Array.from(data.keys())[index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, value),
  };
}

export async function signedInStore(api: FakeApi, user: User = makeUser()): Promise<SessionStore> {
  const store = new SessionStore(memoryStorage());
  store.attach(api as unknown as ApiClient);
  api.auth.login.mockResolvedValue({ access_token: "a", refresh_token: "r", expires_in: 900 });
  api.auth.me.mockResolvedValue(user);
  await store.login("laura@example.com", "password-lunga");
  return store;
}

export function renderApp(api: FakeApi, store: SessionStore, path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <ApiProvider api={api as unknown as ApiClient}>
      <SessionProvider store={store}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </QueryClientProvider>
      </SessionProvider>
    </ApiProvider>,
  );
}
