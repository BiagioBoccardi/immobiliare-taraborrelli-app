import { createApiClient } from "@taraborrelli/api-client";

import { config } from "./config";

/** Public endpoints only for now: browsing needs no account (CLAUDE.md, section 11). */
export const api = createApiClient({ baseUrl: config.apiBaseUrl });
