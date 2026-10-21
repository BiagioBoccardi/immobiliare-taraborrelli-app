import AsyncStorage from "@react-native-async-storage/async-storage";
import { ApiError } from "@taraborrelli/api-client";
import { fireEvent, screen, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import type { ReactNode } from "react";
import type * as ReactNative from "react-native";
import { Share } from "react-native";

import TabsLayout from "../app/(tabs)/_layout";
import Profile from "../app/(tabs)/profilo";
import Login from "../app/accedi";
import ForgotPassword from "../app/password-dimenticata";
import Register from "../app/registrati";
import { api } from "../src/api";
import { ONBOARDING_KEY } from "../src/onboarding";
import { makeSession, page, renderWithProviders, TEST_USER } from "./helpers";

jest.mock("../src/api", () => ({
  api: {
    lead: { myRequests: jest.fn() },
    auth: {
      consents: jest.fn(),
      changeConsent: jest.fn(),
      exportMe: jest.fn(),
      forgotPassword: jest.fn(),
      resetPassword: jest.fn(),
    },
  },
}));

jest.mock("expo-router", () => {
  const { Text: MockText } = jest.requireActual<typeof ReactNative>("react-native");
  const Tabs = ({ children }: { children: ReactNode }) => (
    <>
      <MockText>tabs</MockText>
      {children}
    </>
  );
  Tabs.Screen = () => null;
  return {
    router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
    Redirect: ({ href }: { href: string }) => <MockText>{`redirect:${href}`}</MockText>,
    Tabs,
  };
});

const mockedApi = api as unknown as {
  lead: { myRequests: jest.Mock };
  auth: {
    consents: jest.Mock;
    changeConsent: jest.Mock;
    exportMe: jest.Mock;
    forgotPassword: jest.Mock;
    resetPassword: jest.Mock;
  };
};

const invalidCredentials = new ApiError(401, {
  code: "invalid_credentials",
  message: "",
  details: {},
});

beforeEach(async () => {
  jest.clearAllMocks();
  await AsyncStorage.clear();
  mockedApi.lead.myRequests.mockResolvedValue(page([]));
  mockedApi.auth.consents.mockResolvedValue([]);
});

describe("Session store", () => {
  it("restores the user when a refresh token is stored", async () => {
    const { session } = await makeSession();

    expect(session.getState()).toEqual({ status: "authenticated", user: TEST_USER });
    expect(session.getAccessToken()).toBe("access");
  });

  it("is anonymous without a stored refresh token", async () => {
    const { session, auth } = await makeSession(null);

    expect(session.getState().status).toBe("anonymous");
    expect(auth.refresh).not.toHaveBeenCalled();
  });

  it("is anonymous when the stored refresh token is rejected", async () => {
    const { session, auth, storage } = await makeSession(null);
    storage.value = "expired";
    auth.refresh.mockRejectedValue(
      new ApiError(401, { code: "invalid_token", message: "", details: {} }),
    );

    await session.restore();

    expect(session.getState().status).toBe("anonymous");
    expect(storage.value).toBeNull();
  });

  it("logs in and keeps the refresh token on the device", async () => {
    const { session, auth, storage } = await makeSession(null);

    await session.login("anna@example.test", "una-password-lunga");

    expect(auth.login).toHaveBeenCalledWith("anna@example.test", "una-password-lunga");
    expect(session.getState().user).toEqual(TEST_USER);
    expect(storage.value).toBe("refresh");
  });

  it("forgets the tokens on logout and revokes them on the server", async () => {
    const { session, auth, storage } = await makeSession();

    await session.logout();

    expect(session.getState().status).toBe("anonymous");
    expect(session.getAccessToken()).toBeNull();
    expect(storage.value).toBeNull();
    expect(auth.logout).toHaveBeenCalledWith("refresh");
  });

  it("deletes the account and logs out", async () => {
    const { session, auth } = await makeSession();

    await session.deleteAccount();

    expect(auth.deleteMe).toHaveBeenCalled();
    expect(session.getState().status).toBe("anonymous");
  });
});

describe("Access gate", () => {
  it("sends anonymous users to the login screen", async () => {
    await AsyncStorage.setItem(ONBOARDING_KEY, "1");
    const { session } = await makeSession(null);

    await renderWithProviders(<TabsLayout />, { session });

    expect(await screen.findByText("redirect:/accedi")).toBeTruthy();
  });

  it("shows the welcome screen first on the first launch", async () => {
    const { session } = await makeSession(null);

    await renderWithProviders(<TabsLayout />, { session });

    expect(await screen.findByText("redirect:/benvenuto")).toBeTruthy();
  });

  it("opens the app for logged-in users", async () => {
    await AsyncStorage.setItem(ONBOARDING_KEY, "1");

    await renderWithProviders(<TabsLayout />);

    expect(await screen.findByText("tabs")).toBeTruthy();
  });
});

describe("Login", () => {
  it("logs in and opens the app", async () => {
    const { session, auth } = await makeSession(null);
    await renderWithProviders(<Login />, { session });

    await fireEvent.changeText(screen.getByLabelText("Email"), " anna@example.test ");
    await fireEvent.changeText(screen.getByLabelText("Password"), "una-password-lunga");
    await fireEvent.press(screen.getByRole("button", { name: "Accedi" }));

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/"));
    expect(auth.login).toHaveBeenCalledWith("anna@example.test", "una-password-lunga");
  });

  it("explains wrong credentials", async () => {
    const { session, auth } = await makeSession(null);
    auth.login.mockRejectedValue(invalidCredentials);
    await renderWithProviders(<Login />, { session });

    await fireEvent.changeText(screen.getByLabelText("Email"), "anna@example.test");
    await fireEvent.changeText(screen.getByLabelText("Password"), "sbagliata");
    await fireEvent.press(screen.getByRole("button", { name: "Accedi" }));

    expect(await screen.findByText("Email o password non corretti.")).toBeTruthy();
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("Register", () => {
  it("does not create the account without the privacy consent", async () => {
    const { session, auth } = await makeSession(null);
    await renderWithProviders(<Register />, { session });

    await fireEvent.press(screen.getByRole("button", { name: "Crea account" }));

    expect(await screen.findByText("Serve il consenso per creare l'account")).toBeTruthy();
    expect(auth.register).not.toHaveBeenCalled();
  });

  it("creates the account with the consents and opens the app", async () => {
    const { session, auth } = await makeSession(null);
    await renderWithProviders(<Register />, { session });

    await fireEvent.changeText(screen.getByLabelText("Nome e cognome"), "Anna Bianchi");
    await fireEvent.changeText(screen.getByLabelText("Email"), "anna@example.test");
    await fireEvent.changeText(screen.getByLabelText("Password"), "una-password-lunga");
    await fireEvent.press(
      screen.getByText("Ho letto l'informativa privacy e accetto le condizioni"),
    );
    await fireEvent.press(screen.getByRole("button", { name: "Crea account" }));

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/"));
    expect(auth.register).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: "Anna Bianchi",
        email: "anna@example.test",
        source: "app",
      }),
    );
  });
});

describe("Profile", () => {
  it("shows the user and the requests sent to the agency", async () => {
    mockedApi.lead.myRequests.mockResolvedValue(
      page([
        {
          id: "l1",
          kind: "sell",
          status: "contacted",
          municipality: "Chieti",
          property_type: "apartment",
          created_at: "2026-10-12T10:00:00Z",
        },
      ]),
    );

    await renderWithProviders(<Profile />);

    expect(screen.getByText("Anna Bianchi")).toBeTruthy();
    expect(screen.getByText("anna@example.test")).toBeTruthy();
    expect(await screen.findByText("Vendita · Chieti")).toBeTruthy();
    expect(screen.getByText("Ti abbiamo contattato")).toBeTruthy();
    expect(screen.getByText("Inviata il 12/10/2026")).toBeTruthy();
  });

  it("says when there are no requests yet", async () => {
    await renderWithProviders(<Profile />);

    expect(await screen.findByText("Non hai ancora inviato richieste all'agenzia.")).toBeTruthy();
  });

  it("records the marketing consent with the policy version", async () => {
    mockedApi.auth.changeConsent.mockResolvedValue([]);
    await renderWithProviders(<Profile />);
    const toggle = await screen.findByLabelText("Novità e offerte dall'agenzia");
    await waitFor(() => expect(toggle.props.disabled).toBeFalsy());

    await fireEvent(toggle, "valueChange", true);

    await waitFor(() =>
      expect(mockedApi.auth.changeConsent).toHaveBeenCalledWith(
        expect.objectContaining({ purpose: "marketing", granted: true, policy_version: "2026-01" }),
      ),
    );
  });

  it("shares the exported personal data", async () => {
    mockedApi.auth.exportMe.mockResolvedValue({ user: TEST_USER, consents: [] });
    const share = jest.spyOn(Share, "share").mockResolvedValue({ action: "sharedAction" });
    await renderWithProviders(<Profile />);

    await fireEvent.press(screen.getByText("Scarica i miei dati"));

    await waitFor(() =>
      expect(share).toHaveBeenCalledWith({ message: expect.stringContaining("anna@example.test") }),
    );
  });

  it("logs out", async () => {
    const { session } = await makeSession();
    await renderWithProviders(<Profile />, { session });

    await fireEvent.press(screen.getByText("Esci"));

    await waitFor(() => expect(session.getState().status).toBe("anonymous"));
  });

  it("asks for confirmation before deleting the account", async () => {
    const { session, auth } = await makeSession();
    await renderWithProviders(<Profile />, { session });

    await fireEvent.press(screen.getByText("Elimina account"));
    expect(auth.deleteMe).not.toHaveBeenCalled();
    await fireEvent.press(screen.getByText("Sì, elimina"));

    await waitFor(() => expect(auth.deleteMe).toHaveBeenCalled());
    expect(session.getState().status).toBe("anonymous");
  });
});

describe("Password", () => {
  it("can be shown and hidden while typing", async () => {
    const { session } = await makeSession(null);
    await renderWithProviders(<Login />, { session });
    const field = screen.getByLabelText("Password");
    expect(field.props.secureTextEntry).toBe(true);

    await fireEvent.press(screen.getByRole("button", { name: "Mostra password" }));

    expect(screen.getByLabelText("Password").props.secureTextEntry).toBe(false);
    expect(screen.getByRole("button", { name: "Nascondi password" })).toBeTruthy();
  });

  it("forgotten: the login screen links to the recovery", async () => {
    const { session } = await makeSession(null);
    await renderWithProviders(<Login />, { session });

    await fireEvent.press(screen.getByText("Password dimenticata?"));

    expect(router.push).toHaveBeenCalledWith("/password-dimenticata");
  });

  it("forgotten: sends the code, then saves the new password", async () => {
    mockedApi.auth.forgotPassword.mockResolvedValue(undefined);
    mockedApi.auth.resetPassword.mockResolvedValue(undefined);
    await renderWithProviders(<ForgotPassword />);

    await fireEvent.changeText(screen.getByLabelText("Email"), " anna@example.test ");
    await fireEvent.press(screen.getByRole("button", { name: "Invia il codice" }));
    await fireEvent.changeText(await screen.findByLabelText("Codice di 6 cifre"), "123456");
    await fireEvent.changeText(screen.getByLabelText("Nuova password"), "Nuova-password-1");
    await fireEvent.press(screen.getByRole("button", { name: "Salva la nuova password" }));

    expect(await screen.findByText("Password aggiornata")).toBeTruthy();
    expect(mockedApi.auth.forgotPassword).toHaveBeenCalledWith("anna@example.test");
    expect(mockedApi.auth.resetPassword).toHaveBeenCalledWith(
      "anna@example.test",
      "123456",
      "Nuova-password-1",
    );
  });

  it("forgotten: explains a wrong or expired code", async () => {
    mockedApi.auth.forgotPassword.mockResolvedValue(undefined);
    mockedApi.auth.resetPassword.mockRejectedValue(
      new ApiError(400, { code: "invalid_reset_code", message: "", details: {} }),
    );
    await renderWithProviders(<ForgotPassword />);
    await fireEvent.changeText(screen.getByLabelText("Email"), "anna@example.test");
    await fireEvent.press(screen.getByRole("button", { name: "Invia il codice" }));
    await fireEvent.changeText(await screen.findByLabelText("Codice di 6 cifre"), "000000");
    await fireEvent.changeText(screen.getByLabelText("Nuova password"), "Nuova-password-1");

    await fireEvent.press(screen.getByRole("button", { name: "Salva la nuova password" }));

    expect(
      await screen.findByText(
        "Codice non valido o scaduto. Controlla l'email o chiedine uno nuovo.",
      ),
    ).toBeTruthy();
  });

  it("forgotten: does not call the API with a malformed code", async () => {
    mockedApi.auth.forgotPassword.mockResolvedValue(undefined);
    await renderWithProviders(<ForgotPassword />);
    await fireEvent.changeText(screen.getByLabelText("Email"), "anna@example.test");
    await fireEvent.press(screen.getByRole("button", { name: "Invia il codice" }));
    await fireEvent.changeText(await screen.findByLabelText("Codice di 6 cifre"), "12");

    await fireEvent.press(screen.getByRole("button", { name: "Salva la nuova password" }));

    expect(await screen.findByText("Il codice ha 6 cifre")).toBeTruthy();
    expect(mockedApi.auth.resetPassword).not.toHaveBeenCalled();
  });
});
