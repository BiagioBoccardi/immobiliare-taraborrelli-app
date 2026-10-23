import type { components } from "./generated/property";
import type { HttpClient } from "./http";
import type { Page, PageQuery } from "./common";

type Schemas = components["schemas"];
export type AdminProperty = Schemas["AdminPropertyOut"];
export type AdminPhoto = Schemas["AdminPhotoOut"];
export type ThreeDModel = Schemas["ThreeDModelOut"];
export type PropertyCreate = Schemas["PropertyCreate"];
export type PropertyUpdate = Schemas["PropertyUpdate"];
export type PropertyCard = Schemas["PropertyCard"];
export type PropertyDetail = Schemas["PropertyDetail"];
export type SoldCard = Schemas["SoldCard"];
export type PropertyStatus = Schemas["PropertyStatus"];
export type Contract = Schemas["Contract"];
export type PropertyType = Schemas["PropertyType"];
export type PropertyCondition = Schemas["PropertyCondition"];
export type EnergyClass = Schemas["EnergyClass"];
export type Feature = Schemas["Feature"];
export type TenantType = Schemas["TenantType"];
export type Accommodation = Schemas["Accommodation"];
export type SortOrder = Schemas["SortOrder"];
export type ImportPreview = Schemas["ImportPreview"];
export type ImportRow = Schemas["ImportRowOut"];
export type ImportIssue = Schemas["ImportIssue"];
export type ImportResult = Schemas["ImportResult"];
export type BulkResult = Schemas["BulkResult"];

export interface AdminPropertyFilters extends PageQuery {
  status?: PropertyStatus | undefined;
  contract?: Contract | undefined;
  q?: string | undefined;
}

export interface PropertySearch extends PageQuery {
  contract?: Contract | undefined;
  property_type?: PropertyType[] | undefined;
  municipality?: string | undefined;
  zone?: string | undefined;
  price_min?: number | undefined;
  price_max?: number | undefined;
  surface_min?: number | undefined;
  surface_max?: number | undefined;
  rooms_min?: number | undefined;
  bedrooms_min?: number | undefined;
  bathrooms_min?: number | undefined;
  feature?: Feature[] | undefined;
  energy_class?: EnergyClass[] | undefined;
  featured?: boolean | undefined;
  tenant_type?: TenantType | undefined;
  accommodation?: Accommodation | undefined;
  available_by?: string | undefined;
  min_lat?: number | undefined;
  max_lat?: number | undefined;
  min_lng?: number | undefined;
  max_lng?: number | undefined;
  sort?: SortOrder | undefined;
}

const BASE = "/api/v1/property";
const ADMIN = `${BASE}/admin/properties`;

export function propertyApi(http: HttpClient) {
  return {
    // Public catalog.
    search: (query: PropertySearch) =>
      http.request<Page<PropertyCard>>("GET", `${BASE}/properties`, {
        query: { ...query },
        auth: false,
      }),
    getPublic: (id: string) =>
      http.request<PropertyDetail>("GET", `${BASE}/properties/${id}`, {
        auth: false,
      }),
    listSold: (query: PageQuery) =>
      http.request<Page<SoldCard>>("GET", `${BASE}/sold`, {
        query: { ...query },
        auth: false,
      }),

    // Admin panel.
    list: (filters: AdminPropertyFilters) =>
      http.request<Page<AdminProperty>>("GET", ADMIN, {
        query: { ...filters },
      }),
    get: (id: string) => http.request<AdminProperty>("GET", `${ADMIN}/${id}`),
    create: (data: PropertyCreate) => http.request<AdminProperty>("POST", ADMIN, { json: data }),
    update: (id: string, changes: PropertyUpdate) =>
      http.request<AdminProperty>("PATCH", `${ADMIN}/${id}`, { json: changes }),
    changeStatus: (id: string, status: PropertyStatus) =>
      http.request<AdminProperty>("POST", `${ADMIN}/${id}/status`, {
        json: { status },
      }),
    remove: (id: string) => http.request<undefined>("DELETE", `${ADMIN}/${id}`),
    // Bulk actions on every property matching the list filters (all pages).
    bulkPublish: (filters: Omit<AdminPropertyFilters, "page" | "size">) =>
      http.request<BulkResult>("POST", `${ADMIN}/bulk/publish`, { json: filters }),
    bulkDelete: (filters: Omit<AdminPropertyFilters, "page" | "size">) =>
      http.request<BulkResult>("POST", `${ADMIN}/bulk/delete`, { json: filters }),
    uploadPhoto: (id: string, file: Blob, caption?: string) => {
      const form = new FormData();
      form.append("file", file);
      if (caption) form.append("caption", caption);
      return http.request<AdminProperty>("POST", `${ADMIN}/${id}/photos`, {
        form,
      });
    },
    updatePhoto: (id: string, photoId: string, changes: Schemas["PhotoUpdate"]) =>
      http.request<AdminProperty>("PATCH", `${ADMIN}/${id}/photos/${photoId}`, {
        json: changes,
      }),
    reorderPhotos: (id: string, photoIds: string[]) =>
      http.request<AdminProperty>("PUT", `${ADMIN}/${id}/photos/order`, {
        json: { photo_ids: photoIds },
      }),
    deletePhoto: (id: string, photoId: string) =>
      http.request<AdminProperty>("DELETE", `${ADMIN}/${id}/photos/${photoId}`),

    // 3D model of the property (.glb): a new upload replaces the previous one.
    uploadThreeDModel: (id: string, file: Blob) => {
      const form = new FormData();
      form.append("file", file);
      return http.request<AdminProperty>("PUT", `${ADMIN}/${id}/model-3d`, { form });
    },
    // 3D version of the room in a photo (.glb).
    uploadPhotoThreeD: (id: string, photoId: string, file: Blob) => {
      const form = new FormData();
      form.append("file", file);
      return http.request<AdminProperty>("PUT", `${ADMIN}/${id}/photos/${photoId}/model-3d`, {
        form,
      });
    },
    deletePhotoThreeD: (id: string, photoId: string) =>
      http.request<AdminProperty>("DELETE", `${ADMIN}/${id}/photos/${photoId}/model-3d`),
    deleteThreeDModel: (id: string) =>
      http.request<AdminProperty>("DELETE", `${ADMIN}/${id}/model-3d`),

    // Excel import from the management software: check first, then import the same file.
    previewImport: (file: Blob) => {
      const form = new FormData();
      form.append("file", file);
      return http.request<ImportPreview>("POST", `${ADMIN}/import/preview`, { form });
    },
    runImport: (file: Blob) => {
      const form = new FormData();
      form.append("file", file);
      return http.request<ImportResult>("POST", `${ADMIN}/import`, { form });
    },
    importTemplate: () => http.requestBlob("GET", `${ADMIN}/import/template`),
  };
}

export type PropertyApi = ReturnType<typeof propertyApi>;
