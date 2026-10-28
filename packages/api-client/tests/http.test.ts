import {
  ApiError,
  HttpClient,
  buildQuery,
  createApiClient,
  pageCount,
  type AuthHooks,
} from "../src";

type Call = { url: string; init: RequestInit };

function jsonResponse(status: number, body?: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => (body === undefined ? "" : JSON.stringify(body)),
  } as Response;
}

function fakeFetch(...responses: Response[]) {
  const calls: Call[] = [];
  const impl = async (url: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(url), init: init ?? {} });
    const next = responses.shift();
    if (!next) throw new Error("unexpected request");
    return next;
  };
  return { calls, impl: impl as typeof fetch };
}

function hooks(overrides: Partial<AuthHooks> = {}): AuthHooks {
  return {
    getAccessToken: () => "old-token",
    refreshAccessToken: async () => "new-token",
    onSessionExpired: jest.fn(),
    ...overrides,
  };
}

describe("buildQuery", () => {
  it("repeats array values and skips empty ones", () => {
    const query = buildQuery({
      property_type: ["villa", "house"],
      q: "",
      page: 2,
      x: undefined,
    });

    expect(query).toBe("?property_type=villa&property_type=house&page=2");
  });

  it("encodes special characters", () => {
    expect(buildQuery({ municipality: "Chieti Scalo", q: "a&b=c" })).toBe(
      "?municipality=Chieti%20Scalo&q=a%26b%3Dc",
    );
  });

  it("returns an empty string without parameters", () => {
    expect(buildQuery({ a: null })).toBe("");
  });
});

describe("HttpClient", () => {
  it("sends the bearer token and JSON body", async () => {
    const fetch = fakeFetch(jsonResponse(200, { ok: true }));
    const client = new HttpClient({
      baseUrl: "https://api.test/",
      auth: hooks(),
      fetch: fetch.impl,
    });

    await client.request("POST", "/api/v1/x", { json: { a: 1 } });

    const [call] = fetch.calls;
    expect(call?.url).toBe("https://api.test/api/v1/x");
    expect(call?.init.headers).toMatchObject({
      Authorization: "Bearer old-token",
      "Content-Type": "application/json",
    });
    expect(call?.init.body).toBe('{"a":1}');
  });

  it("does not send the token to public endpoints", async () => {
    const fetch = fakeFetch(jsonResponse(200, {}));
    const client = new HttpClient({
      baseUrl: "",
      auth: hooks(),
      fetch: fetch.impl,
    });

    await client.request("GET", "/public", { auth: false });

    expect(fetch.calls[0]?.init.headers).not.toHaveProperty("Authorization");
  });

  it("turns error responses into ApiError with the backend code", async () => {
    const fetch = fakeFetch(
      jsonResponse(409, {
        code: "photo_required",
        message: "Add a photo",
        details: {},
      }),
    );
    const client = new HttpClient({ baseUrl: "", fetch: fetch.impl });

    const error = await client.request("POST", "/x").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: "photo_required" });
  });

  it("maps non-JSON errors to http_error", async () => {
    const fetch = fakeFetch({
      status: 502,
      ok: false,
      text: async () => "Bad gateway",
    } as Response);
    const client = new HttpClient({ baseUrl: "", fetch: fetch.impl });

    await expect(client.request("GET", "/x")).rejects.toMatchObject({
      status: 502,
      code: "http_error",
    });
  });

  it("maps network failures to network_error", async () => {
    const client = new HttpClient({
      baseUrl: "",
      fetch: (async () => {
        throw new TypeError("Failed to fetch");
      }) as typeof fetch,
    });

    await expect(client.request("GET", "/x")).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });

  it("returns undefined for 204 responses", async () => {
    const fetch = fakeFetch(jsonResponse(204));
    const client = new HttpClient({ baseUrl: "", fetch: fetch.impl });

    await expect(client.request("DELETE", "/x")).resolves.toBeUndefined();
  });

  it("refreshes the token once on 401 and retries", async () => {
    let token = "old-token";
    const fetch = fakeFetch(
      jsonResponse(401, { code: "token_expired", message: "", details: {} }),
      jsonResponse(200, { id: 1 }),
    );
    const auth = hooks({
      getAccessToken: () => token,
      refreshAccessToken: async () => {
        token = "new-token";
        return token;
      },
    });
    const client = new HttpClient({ baseUrl: "", auth, fetch: fetch.impl });

    const result = await client.request<{ id: number }>("GET", "/x");

    expect(result).toEqual({ id: 1 });
    expect(fetch.calls[1]?.init.headers).toMatchObject({
      Authorization: "Bearer new-token",
    });
    expect(auth.onSessionExpired).not.toHaveBeenCalled();
  });

  it("shares one refresh between concurrent 401s", async () => {
    const refresh = jest.fn(async () => "new-token");
    const unauthorized = () =>
      jsonResponse(401, { code: "token_expired", message: "", details: {} });
    const fetch = fakeFetch(
      unauthorized(),
      unauthorized(),
      jsonResponse(200, 1),
      jsonResponse(200, 2),
    );
    const client = new HttpClient({
      baseUrl: "",
      auth: hooks({ refreshAccessToken: refresh }),
      fetch: fetch.impl,
    });

    await Promise.all([client.request("GET", "/a"), client.request("GET", "/b")]);

    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("ends the session when the refresh fails", async () => {
    const fetch = fakeFetch(jsonResponse(401, { code: "token_expired", message: "", details: {} }));
    const auth = hooks({ refreshAccessToken: async () => null });
    const client = new HttpClient({ baseUrl: "", auth, fetch: fetch.impl });

    await expect(client.request("GET", "/x")).rejects.toMatchObject({
      status: 401,
    });
    expect(auth.onSessionExpired).toHaveBeenCalledTimes(1);
  });
});

describe("service clients", () => {
  it("sends the completion token as a header", async () => {
    const fetch = fakeFetch(jsonResponse(204));
    const api = createApiClient({ baseUrl: "", fetch: fetch.impl });

    await api.lead.completeValuation("lead-1", "secret", { bathrooms: 2 });

    expect(fetch.calls[0]?.url).toBe("/api/v1/lead/valuations/lead-1/details");
    expect(fetch.calls[0]?.init.headers).toMatchObject({
      "X-Completion-Token": "secret",
    });
  });

  it("sends photo uploads as multipart form data", async () => {
    const fetch = fakeFetch(jsonResponse(201, {}));
    const api = createApiClient({ baseUrl: "", fetch: fetch.impl });

    await api.property.uploadPhoto("p-1", new Blob(["x"], { type: "image/jpeg" }), "Cucina");

    const body = fetch.calls[0]?.init.body;
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("caption")).toBe("Cucina");
    expect(fetch.calls[0]?.init.headers).not.toHaveProperty("Content-Type");
  });

  it("sends the 3D model as multipart form data with PUT", async () => {
    const fetch = fakeFetch(jsonResponse(200, {}));
    const api = createApiClient({ baseUrl: "", fetch: fetch.impl });

    await api.property.uploadThreeDModel("p-1", new Blob(["glTF"], { type: "model/gltf-binary" }));

    expect(fetch.calls[0]?.url).toBe("/api/v1/property/admin/properties/p-1/model-3d");
    expect(fetch.calls[0]?.init.method).toBe("PUT");
    expect(fetch.calls[0]?.init.body).toBeInstanceOf(FormData);
  });

  it("serializes property search filters", async () => {
    const fetch = fakeFetch(jsonResponse(200, { items: [], total: 0, page: 1, size: 20 }));
    const api = createApiClient({ baseUrl: "", fetch: fetch.impl });

    await api.property.search({
      contract: "rent",
      tenant_type: "students",
      feature: ["garden"],
    });

    expect(fetch.calls[0]?.url).toBe(
      "/api/v1/property/properties?contract=rent&tenant_type=students&feature=garden",
    );
  });
});

describe("pageCount", () => {
  it("rounds up and never returns zero", () => {
    expect(pageCount({ total: 41, size: 20 })).toBe(3);
    expect(pageCount({ total: 0, size: 20 })).toBe(1);
  });
});

describe("owner requests", () => {
  it("send the access token when the user is logged in", async () => {
    const fetch = fakeFetch(jsonResponse(201, {}));
    const api = createApiClient({ baseUrl: "", auth: hooks(), fetch: fetch.impl });

    await api.lead.createOwnerRequest({
      kind: "sell",
      full_name: "Mario Rossi",
      phone: "3330000000",
      municipality: "Chieti",
      property_type: "house",
      intention: "decided",
      consent: { privacy_accepted: true, privacy_policy_version: "2026-01" },
    });

    expect(fetch.calls[0]?.init.headers).toMatchObject({ Authorization: "Bearer old-token" });
  });
});

describe("Excel import", () => {
  it("sends the file for the preview as multipart form data", async () => {
    const preview = { columns: [], ignored_columns: [], missing_columns: [], rows: [] };
    const { calls, impl } = fakeFetch(jsonResponse(200, preview));
    const api = createApiClient({ baseUrl: "http://api.test", fetch: impl, auth: hooks() });

    await api.property.previewImport(new Blob(["x"]));

    expect(calls[0]?.url).toBe("http://api.test/api/v1/property/admin/properties/import/preview");
    expect(calls[0]?.init.body).toBeInstanceOf(FormData);
  });

  it("downloads the template as a blob with the token", async () => {
    const blob = new Blob(["xlsx"]);
    const response = { status: 200, ok: true, blob: async () => blob } as Response;
    const { calls, impl } = fakeFetch(response);
    const api = createApiClient({ baseUrl: "http://api.test", fetch: impl, auth: hooks() });

    const result = await api.property.importTemplate();

    expect(result).toBe(blob);
    expect((calls[0]?.init.headers as Record<string, string>).Authorization).toBe(
      "Bearer old-token",
    );
  });

  it("turns a failed download into ApiError", async () => {
    const { impl } = fakeFetch(
      jsonResponse(403, { code: "forbidden", message: "No", details: {} }),
    );
    const api = createApiClient({ baseUrl: "http://api.test", fetch: impl, auth: hooks() });

    await expect(api.property.importTemplate()).rejects.toMatchObject({ code: "forbidden" });
  });
});

describe("password reset", () => {
  it("asks for a code without sending the access token", async () => {
    const { calls, impl } = fakeFetch(jsonResponse(202));
    const api = createApiClient({ baseUrl: "http://api.test", fetch: impl, auth: hooks() });

    await api.auth.forgotPassword("anna@example.test");

    expect(calls[0]?.url).toBe("http://api.test/api/v1/auth/password/forgot");
    expect(calls[0]?.init.body).toBe(JSON.stringify({ email: "anna@example.test" }));
    expect((calls[0]?.init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("sends code and new password", async () => {
    const { calls, impl } = fakeFetch(jsonResponse(204));
    const api = createApiClient({ baseUrl: "http://api.test", fetch: impl });

    await api.auth.resetPassword("anna@example.test", "123456", "Nuova-password-1");

    expect(calls[0]?.init.body).toBe(
      JSON.stringify({
        email: "anna@example.test",
        code: "123456",
        new_password: "Nuova-password-1",
      }),
    );
  });
});

describe("bulk property actions", () => {
  it("sends the list filters to the bulk endpoint", async () => {
    const { calls, impl } = fakeFetch(jsonResponse(200, { done: 2, skipped: [] }));
    const api = createApiClient({ baseUrl: "http://api.test", fetch: impl, auth: hooks() });

    const result = await api.property.bulkPublish({ status: "draft", contract: undefined });

    expect(result.done).toBe(2);
    expect(calls[0]?.url).toBe("http://api.test/api/v1/property/admin/properties/bulk/publish");
    expect(calls[0]?.init.body).toBe(JSON.stringify({ status: "draft" }));
  });
});
