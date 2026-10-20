import {
  ApiError,
  type ConsentPurpose,
  type Contract,
  type PropertySearch,
} from "@taraborrelli/api-client";
import {
  useInfiniteQuery,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api } from "./api";
import { privacy } from "./config";

const PAGE_SIZE = 20;

export function useFeatured(contract: Contract) {
  return useQuery({
    queryKey: ["featured", contract],
    queryFn: () => api.property.search({ contract, featured: true, size: 10 }),
  });
}

export function useLatest(contract: Contract, size = 5) {
  return useQuery({
    queryKey: ["latest", contract, size],
    queryFn: () => api.property.search({ contract, sort: "newest", size }),
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

/** Requests the user sent to the agency (valuations, "voglio vendere", "voglio affittare"). */
export function useMyRequests() {
  return useQuery({
    queryKey: ["me", "requests"],
    queryFn: () => api.lead.myRequests({ size: 20 }),
  });
}

export function useMyConsents() {
  return useQuery({
    queryKey: ["me", "consents"],
    queryFn: () => api.auth.consents(),
  });
}

export function useChangeConsent() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ purpose, granted }: { purpose: ConsentPurpose; granted: boolean }) =>
      api.auth.changeConsent({ purpose, granted, policy_version: privacy.version, source: "app" }),
    onSuccess: (consents) => client.setQueryData(["me", "consents"], consents),
  });
}
