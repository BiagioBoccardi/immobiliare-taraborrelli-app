import { ApiError, type ApiClient } from "@taraborrelli/api-client";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SessionStore } from "../src/auth/session";
import { fakeApi, memoryStorage, renderApp } from "./helpers";

function anonymousStore(api: ReturnType<typeof fakeApi>): SessionStore {
  const store = new SessionStore(memoryStorage());
  store.attach(api as unknown as ApiClient);
  store.onSessionExpired();
  return store;
}

describe("password on the login page", () => {
  it("can be shown and hidden", async () => {
    const api = fakeApi();
    renderApp(api, anonymousStore(api), "/login");
    const field = await screen.findByLabelText("Password");
    expect(field).toHaveAttribute("type", "password");

    await userEvent.click(screen.getByRole("button", { name: "Mostra password" }));

    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Nascondi password" })).toBeVisible();
  });

  it("links to the password recovery", async () => {
    const api = fakeApi();
    renderApp(api, anonymousStore(api), "/login");

    await userEvent.click(await screen.findByRole("link", { name: "Password dimenticata?" }));

    expect(await screen.findByRole("heading", { name: "Password dimenticata" })).toBeVisible();
  });
});

describe("forgotten password", () => {
  async function askCode(api: ReturnType<typeof fakeApi>) {
    api.auth.forgotPassword.mockResolvedValue(undefined);
    renderApp(api, anonymousStore(api), "/forgot-password");
    await userEvent.type(await screen.findByLabelText("Email"), "laura@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Invia il codice" }));
    await screen.findByRole("heading", { name: "Controlla la tua email" });
  }

  it("sends the code, then saves the new password", async () => {
    const api = fakeApi();
    api.auth.resetPassword.mockResolvedValue(undefined);
    await askCode(api);

    await userEvent.type(screen.getByLabelText("Codice di 6 cifre"), "123456");
    await userEvent.type(
      screen.getByLabelText("Nuova password (almeno 10 caratteri)"),
      "Nuova-password-1",
    );
    await userEvent.click(screen.getByRole("button", { name: "Salva la nuova password" }));

    expect(await screen.findByRole("heading", { name: "Password aggiornata" })).toBeVisible();
    expect(api.auth.forgotPassword).toHaveBeenCalledWith("laura@example.com");
    expect(api.auth.resetPassword).toHaveBeenCalledWith(
      "laura@example.com",
      "123456",
      "Nuova-password-1",
    );
  });

  it("explains a wrong or expired code", async () => {
    const api = fakeApi();
    api.auth.resetPassword.mockRejectedValue(
      new ApiError(400, { code: "invalid_reset_code", message: "", details: {} }),
    );
    await askCode(api);

    await userEvent.type(screen.getByLabelText("Codice di 6 cifre"), "000000");
    await userEvent.type(
      screen.getByLabelText("Nuova password (almeno 10 caratteri)"),
      "Nuova-password-1",
    );
    await userEvent.click(screen.getByRole("button", { name: "Salva la nuova password" }));

    expect(
      await screen.findByText(
        "Codice non valido o scaduto. Controlla l'email o chiedine uno nuovo.",
      ),
    ).toBeVisible();
  });

  it("checks code and password before calling the API", async () => {
    const api = fakeApi();
    await askCode(api);

    await userEvent.type(screen.getByLabelText("Codice di 6 cifre"), "12");
    await userEvent.click(screen.getByRole("button", { name: "Salva la nuova password" }));

    expect(screen.getByText("Il codice ha 6 cifre.")).toBeVisible();
    expect(screen.getByText("La password deve avere almeno 10 caratteri.")).toBeVisible();
    expect(api.auth.resetPassword).not.toHaveBeenCalled();
  });

  it("sends the code again on request", async () => {
    const api = fakeApi();
    await askCode(api);

    await userEvent.click(screen.getByRole("button", { name: "Non è arrivato? Invia di nuovo" }));

    expect(await screen.findByText("Ti abbiamo inviato un nuovo codice.")).toBeVisible();
    expect(api.auth.forgotPassword).toHaveBeenCalledTimes(2);
  });
});
