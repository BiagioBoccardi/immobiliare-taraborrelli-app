import type {
  Contract,
  Feature,
  PropertySearch,
  PropertyType,
  TenantType,
} from "@taraborrelli/api-client";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

/** Search filters shared by the Home, the search screen and the filters screen. */
export interface SearchFilters {
  contract: Contract;
  municipality: string;
  propertyTypes: PropertyType[];
  priceMin: string;
  priceMax: string;
  roomsMin: number | null;
  features: Feature[];
  tenantType: TenantType | null;
}

export const DEFAULT_FILTERS: SearchFilters = {
  contract: "sale",
  municipality: "",
  propertyTypes: [],
  priceMin: "",
  priceMax: "",
  roomsMin: null,
  features: [],
  tenantType: null,
};

const toNumber = (value: string): number | undefined => {
  const digits = value.replace(/\D/g, "");
  return digits ? Number(digits) : undefined;
};

/** Converts the filters into the catalog API query. */
export function toQuery(filters: SearchFilters): PropertySearch {
  return {
    contract: filters.contract,
    municipality: filters.municipality.trim() || undefined,
    property_type: filters.propertyTypes.length ? filters.propertyTypes : undefined,
    price_min: toNumber(filters.priceMin),
    price_max: toNumber(filters.priceMax),
    rooms_min: filters.roomsMin ?? undefined,
    feature: filters.features.length ? filters.features : undefined,
    tenant_type: filters.contract === "rent" ? (filters.tenantType ?? undefined) : undefined,
    sort: "newest",
  };
}

/** Number of filters set beyond contract and municipality, shown on the filters button. */
export function activeFilterCount(filters: SearchFilters): number {
  return [
    filters.propertyTypes.length > 0,
    filters.priceMin !== "" || filters.priceMax !== "",
    filters.roomsMin !== null,
    filters.features.length > 0,
    filters.contract === "rent" && filters.tenantType !== null,
  ].filter(Boolean).length;
}

interface SearchValue {
  filters: SearchFilters;
  setFilters: (next: SearchFilters) => void;
  update: (changes: Partial<SearchFilters>) => void;
}

const SearchContext = createContext<SearchValue | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const value = useMemo<SearchValue>(
    () => ({
      filters,
      setFilters,
      update: (changes) => setFilters((current) => ({ ...current, ...changes })),
    }),
    [filters],
  );
  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>;
}

export function useSearch(): SearchValue {
  const value = useContext(SearchContext);
  if (!value) throw new Error("useSearch must be used inside SearchProvider");
  return value;
}
