import type {
  AdminProperty,
  AdminPropertyFilters,
  LeadFilters,
  LeadUpdate,
  PropertyCreate,
  PropertyStatus,
  PropertyUpdate,
  Role,
  StaffCreate,
  UserUpdate,
} from "@taraborrelli/api-client";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "./ApiContext";

export const keys = {
  leads: (filters: LeadFilters) => ["leads", filters] as const,
  lead: (id: string) => ["lead", id] as const,
  properties: (filters: AdminPropertyFilters) => ["properties", filters] as const,
  property: (id: string) => ["property", id] as const,
  users: (role: Role | undefined, page: number) => ["users", role, page] as const,
};

// Leads ----------------------------------------------------------------------------------

export function useLeads(filters: LeadFilters) {
  const api = useApi();
  return useQuery({
    queryKey: keys.leads(filters),
    queryFn: () => api.lead.listLeads(filters),
    placeholderData: keepPreviousData,
  });
}

export function useLead(id: string) {
  const api = useApi();
  return useQuery({ queryKey: keys.lead(id), queryFn: () => api.lead.getLead(id) });
}

export function useUpdateLead(id: string) {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (changes: LeadUpdate) => api.lead.updateLead(id, changes),
    onSuccess: (lead) => {
      client.setQueryData(keys.lead(id), lead);
      void client.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useDeleteLead() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.lead.deleteLead(id),
    onSuccess: (_, id) => {
      client.removeQueries({ queryKey: keys.lead(id) });
      void client.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

/** Every property (all pages), e.g. to match bulk photos with the management code. */
export function useAllProperties() {
  const api = useApi();
  return useQuery({
    queryKey: ["properties", "all"],
    queryFn: async () => {
      const size = 100;
      const first = await api.property.list({ page: 1, size });
      const items = [...first.items];
      for (let page = 2; (page - 1) * size < first.total; page++) {
        items.push(...(await api.property.list({ page, size })).items);
      }
      return items;
    },
  });
}

/** Publish from the list, without opening the property. */
export function usePublishProperty() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.property.changeStatus(id, "published"),
    onSuccess: (property) => {
      client.setQueryData(keys.property(property.id), property);
      void client.invalidateQueries({ queryKey: ["properties"] });
    },
  });
}

type ListFilters = Omit<AdminPropertyFilters, "page" | "size">;

export function useBulkPublish() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (filters: ListFilters) => api.property.bulkPublish(filters),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["properties"] }),
  });
}

export function useBulkDelete() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (filters: ListFilters) => api.property.bulkDelete(filters),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["properties"] }),
  });
}

// Password reset (public) ----------------------------------------------------------------

export function useForgotPassword() {
  const api = useApi();
  return useMutation({ mutationFn: (email: string) => api.auth.forgotPassword(email) });
}

export function useResetPassword() {
  const api = useApi();
  return useMutation({
    mutationFn: ({ email, code, password }: { email: string; code: string; password: string }) =>
      api.auth.resetPassword(email, code, password),
  });
}

// Properties -----------------------------------------------------------------------------

export function useProperties(filters: AdminPropertyFilters) {
  const api = useApi();
  return useQuery({
    queryKey: keys.properties(filters),
    queryFn: () => api.property.list(filters),
    placeholderData: keepPreviousData,
  });
}

export function useProperty(id: string) {
  const api = useApi();
  return useQuery({ queryKey: keys.property(id), queryFn: () => api.property.get(id) });
}

/** Every property mutation returns the updated property: store it and refresh the lists. */
function usePropertyMutation<TArgs>(id: string, mutate: (args: TArgs) => Promise<AdminProperty>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: mutate,
    onSuccess: (property) => {
      client.setQueryData(keys.property(id), property);
      void client.invalidateQueries({ queryKey: ["properties"] });
    },
  });
}

export function useCreateProperty() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: PropertyCreate) => api.property.create(data),
    onSuccess: (property) => {
      client.setQueryData(keys.property(property.id), property);
      void client.invalidateQueries({ queryKey: ["properties"] });
    },
  });
}

export function useUpdateProperty(id: string) {
  const api = useApi();
  return usePropertyMutation(id, (changes: PropertyUpdate) => api.property.update(id, changes));
}

export function useChangeStatus(id: string) {
  const api = useApi();
  return usePropertyMutation(id, (status: PropertyStatus) => api.property.changeStatus(id, status));
}

export function useUploadPhoto(id: string) {
  const api = useApi();
  return usePropertyMutation(id, (file: File) => api.property.uploadPhoto(id, file));
}

export function useUpdatePhoto(id: string) {
  const api = useApi();
  return usePropertyMutation(
    id,
    ({ photoId, ...changes }: { photoId: string; caption?: string; show_when_sold?: boolean }) =>
      api.property.updatePhoto(id, photoId, changes),
  );
}

export function useReorderPhotos(id: string) {
  const api = useApi();
  return usePropertyMutation(id, (photoIds: string[]) => api.property.reorderPhotos(id, photoIds));
}

export function useDeletePhoto(id: string) {
  const api = useApi();
  return usePropertyMutation(id, (photoId: string) => api.property.deletePhoto(id, photoId));
}

export function useDeleteProperty() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.property.remove(id),
    onSuccess: (_, id) => {
      client.removeQueries({ queryKey: keys.property(id) });
      void client.invalidateQueries({ queryKey: ["properties"] });
    },
  });
}

export function usePreviewImport() {
  const api = useApi();
  return useMutation({ mutationFn: (file: File) => api.property.previewImport(file) });
}

export function useRunImport() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.property.runImport(file),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["properties"] });
    },
  });
}

// Staff accounts -------------------------------------------------------------------------

export function useUsers(role: Role | undefined, page: number) {
  const api = useApi();
  return useQuery({
    queryKey: keys.users(role, page),
    queryFn: () => api.auth.listUsers({ role, page, size: 20 }),
    placeholderData: keepPreviousData,
  });
}

export function useCreateStaff() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: StaffCreate) => api.auth.createStaff(data),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useUpdateUser() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: UserUpdate }) =>
      api.auth.updateUser(id, changes),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["users"] }),
  });
}
