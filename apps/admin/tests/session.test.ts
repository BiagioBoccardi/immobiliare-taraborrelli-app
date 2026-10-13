import { ApiError, type ApiClient } from "@taraborrelli/api-client";

import { SessionStore } from "../src/auth/session";
import { fakeApi, makeUser, memoryStorage } from "./helpers";

const TOKENS = { access_token: "access-1", refresh_token: "refresh-1", expires_in: 900 };

function setup() {
  const api = fakeApi();
  const storage = memoryStorage();
  const store = new SessionStore(storage);
  store.attach(api as unknown as ApiClient);
  return { api, storage, store };
}

describe("SessionStore", () => {
  it("logs in staff and keeps only the refresh token in storage", async () => {
    const { api, storage, store } = setup();
    api.auth.login.mockResolvedValue(TOKENS);
    api.auth.me.mockResolvedValue(makeUser());

    await store.login("laura@example.com", "password-lunga");

    expect(store.getState().status).toBe("authenticated");
    expect(store.getAccessToken()).toBe("access-1");
    expect(storage.getItem("taraborrelli.admin.refresh")).toBe("refresh-1");
    expect(JSON.stringify(storage)).not.toContain("access-1");
  });

  it("refuses app users and ends their session", async () => {
    const { api, storage, store } = setup();
    api.auth.login.mockResolvedValue(TOKENS);
    api.auth.me.mockResolvedValue(makeUser({ role: "user" }));
    api.auth.logout.mockResolvedValue(undefined);

    await store.login("cliente@example.com", "password-lunga");

    expect(store.getState()).toMatchObject({ status: "anonymous", error: "not_staff" });
    expect(api.auth.logout).toHaveBeenCalledWith("refresh-1");
    expect(storage.getItem("taraborrelli.admin.refresh")).toBeNull();
  });

  it("propagates login errors without changing state", async () => {
    const { api, store } = setup();
    api.auth.login.mockRejectedValue(
      new ApiError(401, { code: "invalid_credentials", message: "", details: {} }),
    );

    await expect(store.login("a@example.com", "x")).rejects.toMatchObject({
      code: "invalid_credentials",
    });
    expect(store.getState().status).toBe("loading");
  });

  it("restores the session from the stored refresh token", async () => {
    const { api, storage, store } = setup();
    storage.setItem("taraborrelli.admin.refresh", "refresh-0");
    api.auth.refresh.mockResolvedValue(TOKENS);
    api.auth.me.mockResolvedValue(makeUser());

    await store.restore();

    expect(api.auth.refresh).toHaveBeenCalledWith("refresh-0");
    expect(store.getState().status).toBe("authenticated");
    expect(storage.getItem("taraborrelli.admin.refresh")).toBe("refresh-1");
  });

  it("becomes anonymous when there is nothing to restore", async () => {
    const { api, store } = setup();

    await store.restore();

    expect(api.auth.refresh).not.toHaveBeenCalled();
    expect(store.getState()).toMatchObject({ status: "anonymous", error: null });
  });

  it("clears everything when the session expires", async () => {
    const { api, storage, store } = setup();
    api.auth.login.mockResolvedValue(TOKENS);
    api.auth.me.mockResolvedValue(makeUser());
    await store.login("laura@example.com", "password-lunga");
    const listener = jest.fn();
    store.subscribe(listener);

    store.onSessionExpired();

    expect(store.getAccessToken()).toBeNull();
    expect(storage.getItem("taraborrelli.admin.refresh")).toBeNull();
    expect(store.getState()).toMatchObject({ status: "anonymous", error: "unauthorized" });
    expect(listener).toHaveBeenCalled();
  });

  it("returns null when the refresh is rejected", async () => {
    const { api, storage, store } = setup();
    storage.setItem("taraborrelli.admin.refresh", "stolen");
    api.auth.refresh.mockRejectedValue(new Error("401"));

    await expect(store.refreshAccessToken()).resolves.toBeNull();
  });
});
