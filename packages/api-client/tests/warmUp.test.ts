import { warmUpServices } from "../src/warmUp";

const ok = { ok: true } as Response;
const unavailable = { ok: false } as Response;
const noSleep = () => Promise.resolve();

describe("warmUpServices", () => {
  it("calls the health route of every service once when they are awake", async () => {
    const fetchImpl = jest.fn().mockResolvedValue(ok);

    const awake = await warmUpServices({ fetchImpl, sleep: noSleep });

    expect(awake).toEqual(["auth", "lead", "property"]);
    expect(fetchImpl.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/auth/health",
      "/api/v1/lead/health",
      "/api/v1/property/health",
    ]);
  });

  it("tries again while a service is starting", async () => {
    let leadCalls = 0;
    const fetchImpl = jest.fn((input: RequestInfo | URL) => {
      if (String(input).includes("/lead/")) {
        leadCalls += 1;
        if (leadCalls === 1) return Promise.reject(new TypeError("proxy timeout"));
        if (leadCalls === 2) return Promise.resolve(unavailable);
      }
      return Promise.resolve(ok);
    });

    const awake = await warmUpServices({ fetchImpl, sleep: noSleep });

    expect(awake).toEqual(["auth", "lead", "property"]);
    expect(leadCalls).toBe(3);
  });

  it("gives up after the last attempt without throwing", async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new TypeError("offline"));

    const awake = await warmUpServices({ fetchImpl, sleep: noSleep, maxAttempts: 2 });

    expect(awake).toEqual([]);
    expect(fetchImpl).toHaveBeenCalledTimes(6);
  });
});
