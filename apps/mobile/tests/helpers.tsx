import type {
  ApiClient,
  PropertyCard,
  PropertyDetail,
  TokenPair,
  User,
} from "@taraborrelli/api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react-native";
import type { ReactElement } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { FavoritesProvider } from "../src/favorites";
import { SearchProvider } from "../src/search";
import { SessionProvider, SessionStore, type TokenStorage } from "../src/session";

const metrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 0, left: 0, right: 0, bottom: 0 },
};

export const TEST_USER: User = {
  id: "u1",
  email: "anna@example.test",
  full_name: "Anna Bianchi",
  role: "user",
  is_active: true,
  created_at: "2026-10-01T09:00:00Z",
  last_login_at: null,
};

export const TEST_TOKENS: TokenPair = {
  access_token: "access",
  refresh_token: "refresh",
  expires_in: 900,
  token_type: "bearer",
};

/** Refresh token kept in memory instead of the phone's keychain. */
export function memoryStorage(
  initial: string | null = null,
): TokenStorage & { value: string | null } {
  const storage = {
    value: initial,
    get: () => Promise.resolve(storage.value),
    set: (value: string) => {
      storage.value = value;
      return Promise.resolve();
    },
    remove: () => {
      storage.value = null;
      return Promise.resolve();
    },
  };
  return storage;
}

export interface FakeAuthApi {
  login: jest.Mock;
  register: jest.Mock;
  refresh: jest.Mock;
  logout: jest.Mock;
  me: jest.Mock;
  deleteMe: jest.Mock;
}

export function fakeAuthApi(user: User = TEST_USER): FakeAuthApi {
  return {
    login: jest.fn().mockResolvedValue(TEST_TOKENS),
    register: jest.fn().mockResolvedValue(TEST_TOKENS),
    refresh: jest.fn().mockResolvedValue(TEST_TOKENS),
    logout: jest.fn().mockResolvedValue(undefined),
    me: jest.fn().mockResolvedValue(user),
    deleteMe: jest.fn().mockResolvedValue(undefined),
  };
}

/** A session store talking to a fake auth API; logged in as `user` unless `null`. */
export async function makeSession(user: User | null = TEST_USER) {
  const auth = fakeAuthApi(user ?? TEST_USER);
  const storage = memoryStorage(user ? "refresh" : null);
  const session = new SessionStore(storage);
  session.attach({ auth } as unknown as ApiClient);
  await session.restore();
  return { session, auth, storage };
}

export async function renderWithProviders(
  ui: ReactElement,
  { session }: { session?: SessionStore } = {},
) {
  const store = session ?? (await makeSession()).session;
  const userId = store.getState().user?.id ?? "anonymous";
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false, gcTime: Infinity },
    },
  });
  return await render(
    <SafeAreaProvider initialMetrics={metrics}>
      <SessionProvider store={store}>
        <QueryClientProvider client={client}>
          <FavoritesProvider userId={userId}>
            <SearchProvider>{ui}</SearchProvider>
          </FavoritesProvider>
        </QueryClientProvider>
      </SessionProvider>
    </SafeAreaProvider>,
  );
}

export function makeCard(overrides: Partial<PropertyCard> = {}): PropertyCard {
  return {
    id: "p1",
    reference: "TR00001",
    status: "published",
    contract: "sale",
    property_type: "apartment",
    title: "Trilocale luminoso con balcone",
    price: 139000,
    municipality: "Chieti",
    zone: "Centro",
    surface_sqm: 95,
    rooms: 3,
    bedrooms: 2,
    bathrooms: 1,
    is_featured: true,
    cover_photo: { id: "f1", url: "https://media.test/f1.jpg", caption: null },
    coordinates: null,
    available_from: null,
    published_at: "2026-10-13T09:00:00Z",
    ...overrides,
  };
}

export function makeDetail(overrides: Partial<PropertyDetail> = {}): PropertyDetail {
  return {
    ...makeCard(),
    description: "Appartamento al secondo piano.",
    condominium_fees: 80,
    floor: 2,
    total_floors: 4,
    year_built: 1990,
    condition: "good",
    energy_class: "C",
    features: ["balcony", "elevator"],
    tenant_types: [],
    accommodation: null,
    photos: [{ id: "f1", url: "https://media.test/f1.jpg", caption: null }],
    three_d_model: null,
    ...overrides,
  };
}

export function page<T>(items: T[]) {
  return { items, total: items.length, page: 1, size: 20 };
}
