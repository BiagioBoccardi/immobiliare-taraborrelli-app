import { ApiError, type Contract, type PropertySearch } from "@taraborrelli/api-client";
import { useInfiniteQuery, useQueries, useQuery } from "@tanstack/react-query";

import { api } from "./api";

const PAGE_SIZE = 20;

export function useFeatured(contract: Contract) {
  return useQuery({
    queryKey: ["featured", contract],
    queryFn: () => api.property.search({ contract, featured: true, size: 10 }),
  });
}

export function useLatest(contract: Contract) {
  return useQuery({
    queryKey: ["latest", contract],
    queryFn: () => api.property.search({ contract, sort: "newest", size: 5 }),
  });
}

export function useSearchResults(query: PropertySearch) {
  return useInfiniteQuery({
    queryKey: ["search", query],
    initialPageParam: 1,
    queryFn: ({ pageParam }) => api.property.search({ ...query, page: pageParam, size: PAGE_SIZE }),
    getNextPageParam: (last) => (last.page * last.size < last.total ? last.page + 1 : undefined),
  });
}

export function useProperty(id: string) {
  return useQuery({
    queryKey: ["property", id],
    queryFn: () => api.property.getPublic(id),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
}

/** Favorites: one request per saved property; removed or sold properties answer 404. */
export function useFavoriteProperties(ids: string[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: ["property", id],
      queryFn: () => api.property.getPublic(id),
      retry: false,
    })),
  });
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
