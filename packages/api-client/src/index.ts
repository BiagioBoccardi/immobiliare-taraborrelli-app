import { authApi } from "./auth";
import { HttpClient, type ClientOptions } from "./http";
import { leadApi } from "./lead";
import { propertyApi } from "./property";

export * from "./auth";
export * from "./common";
export * from "./http";
export * from "./lead";
export * from "./property";

export function createApiClient(options: ClientOptions) {
  const http = new HttpClient(options);
  return {
    auth: authApi(http),
    lead: leadApi(http),
    property: propertyApi(http),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
