import type { PropertyCard, PropertyDetail } from "@taraborrelli/api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react-native";
import type { ReactElement } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { FavoritesProvider } from "../src/favorites";
import { SearchProvider } from "../src/search";

const metrics = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 0, left: 0, right: 0, bottom: 0 },
};

export async function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false, gcTime: Infinity },
    },
  });
  return await render(
    <SafeAreaProvider initialMetrics={metrics}>
      <QueryClientProvider client={client}>
        <FavoritesProvider>
          <SearchProvider>{ui}</SearchProvider>
        </FavoritesProvider>
      </QueryClientProvider>
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
    ...overrides,
  };
}

export function page<T>(items: T[]) {
  return { items, total: items.length, page: 1, size: 20 };
}
