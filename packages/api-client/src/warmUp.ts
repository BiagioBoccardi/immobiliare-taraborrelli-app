/**
 * Wakes the API services up as soon as the admin panel or the web app opens.
 *
 * On Render's free plan each service sleeps after 15 minutes without requests and needs
 * about a minute to start, while Netlify's proxy gives up after 26 seconds. Calling each
 * service's /health right away (and again until it answers) means that by the time someone
 * has typed their password the services are usually awake.
 */
export const SERVICES = ["auth", "lead", "property"] as const;

interface WarmUpOptions {
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  /** Pause between two attempts on the same service. */
  intervalMs?: number;
  /** Stop trying after this many attempts per service. */
  maxAttempts?: number;
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

async function wake(service: string, options: Required<WarmUpOptions>): Promise<boolean> {
  for (let attempt = 1; attempt <= options.maxAttempts; attempt += 1) {
    try {
      const response = await options.fetchImpl(`/api/v1/${service}/health`, { cache: "no-store" });
      if (response.ok) return true;
    } catch {
      // Network error or proxy timeout while the service starts: try again.
    }
    if (attempt < options.maxAttempts) await options.sleep(options.intervalMs);
  }
  return false;
}

/** Resolves to the services that answered. Never throws. */
export async function warmUpServices(options: WarmUpOptions = {}): Promise<string[]> {
  const settings: Required<WarmUpOptions> = {
    fetchImpl: options.fetchImpl ?? ((...args) => fetch(...args)),
    sleep: options.sleep ?? wait,
    intervalMs: options.intervalMs ?? 5_000,
    maxAttempts: options.maxAttempts ?? 12,
  };
  const results = await Promise.all(SERVICES.map((service) => wake(service, settings)));
  return SERVICES.filter((_, index) => results[index]);
}
