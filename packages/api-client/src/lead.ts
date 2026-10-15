import type { components } from "./generated/lead";
import type { HttpClient } from "./http";
import type { Page, PageQuery } from "./common";

type Schemas = components["schemas"];
export type Lead = Schemas["LeadOut"];
export type LeadUpdate = Schemas["LeadUpdate"];
export type LeadKind = Schemas["LeadKind"];
export type LeadStatus = Schemas["LeadStatus"];
export type LeadPriority = Schemas["LeadPriority"];
export type OwnerIntention = Schemas["OwnerIntention"];
export type ValuationCreate = Schemas["ValuationCreate"];
export type ValuationCreated = Schemas["ValuationCreatedOut"];
export type ValuationDetails = Schemas["ValuationDetails"];
export type OwnerRequestCreate = Schemas["OwnerRequestCreate"];
export type LeadCreated = Schemas["LeadCreatedOut"];
export type MyRequest = Schemas["MyRequestOut"];

export interface LeadFilters extends PageQuery {
  kind?: LeadKind | undefined;
  status?: LeadStatus | undefined;
  priority?: LeadPriority | undefined;
  due_for_contact?: boolean | undefined;
}

const BASE = "/api/v1/lead";

export function leadApi(http: HttpClient) {
  return {
    // Owner forms. They work without an account; a logged-in user's token links the request.
    createValuation: (data: ValuationCreate) =>
      http.request<ValuationCreated>("POST", `${BASE}/valuations`, { json: data }),
    completeValuation: (id: string, completionToken: string, details: ValuationDetails) =>
      http.request<undefined>("PUT", `${BASE}/valuations/${id}/details`, {
        json: details,
        headers: { "X-Completion-Token": completionToken },
        auth: false,
      }),
    createOwnerRequest: (data: OwnerRequestCreate) =>
      http.request<LeadCreated>("POST", `${BASE}/owner-requests`, { json: data }),
    myRequests: (query: PageQuery) =>
      http.request<Page<MyRequest>>("GET", `${BASE}/me/requests`, { query: { ...query } }),

    // Staff CRM.
    listLeads: (filters: LeadFilters) =>
      http.request<Page<Lead>>("GET", `${BASE}/leads`, {
        query: { ...filters },
      }),
    getLead: (id: string) => http.request<Lead>("GET", `${BASE}/leads/${id}`),
    updateLead: (id: string, changes: LeadUpdate) =>
      http.request<Lead>("PATCH", `${BASE}/leads/${id}`, { json: changes }),
    deleteLead: (id: string) => http.request<undefined>("DELETE", `${BASE}/leads/${id}`),
  };
}

export type LeadApi = ReturnType<typeof leadApi>;
