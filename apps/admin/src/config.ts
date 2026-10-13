/** Runtime configuration, injected at build time by Vite (see vite.config.ts). */
declare const __API_BASE_URL__: string;

export const config = {
  apiBaseUrl: __API_BASE_URL__,
};
