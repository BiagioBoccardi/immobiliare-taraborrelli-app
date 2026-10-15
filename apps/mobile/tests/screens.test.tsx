import AsyncStorage from "@react-native-async-storage/async-storage";
import { ApiError } from "@taraborrelli/api-client";
import { fireEvent, screen, waitFor } from "@testing-library/react-native";
import { Linking } from "react-native";

import Home from "../app/(tabs)/index";
import Favorites from "../app/(tabs)/preferiti";
import Sell from "../app/(tabs)/vendi";
import PropertyScreen from "../app/immobile/[id]";
import { api } from "../src/api";
import { FAVORITES_KEY } from "../src/favorites";
import { makeCard, makeDetail, page, renderWithProviders } from "./helpers";

jest.mock("../src/api", () => ({
  api: {
    property: { search: jest.fn(), getPublic: jest.fn() },
    lead: { createOwnerRequest: jest.fn() },
  },
}));

jest.mock("expo-router", () => ({
  router: {
    push: jest.fn(),
    navigate: jest.fn(),
    back: jest.fn(),
    replace: jest.fn(),
    canGoBack: () => true,
  },
  useLocalSearchParams: () => ({ id: "p1" }),
}));

const mockedApi = api as unknown as {
  property: { search: jest.Mock; getPublic: jest.Mock };
  lead: { createOwnerRequest: jest.Mock };
};

beforeEach(async () => {
  jest.clearAllMocks();
  await AsyncStorage.clear();
});

describe("Home", () => {
  it("shows the three main actions and featured properties", async () => {
    mockedApi.property.search.mockResolvedValue(page([makeCard()]));

    await renderWithProviders(<Home />);

    expect(screen.getByText("Cerca casa")).toBeTruthy();
    expect(screen.getByText("Vendi casa")).toBeTruthy();
    expect(screen.getByText("Contattaci")).toBeTruthy();
    expect(await screen.findAllByText("Trilocale luminoso con balcone")).not.toHaveLength(0);
    expect(mockedApi.property.search).toHaveBeenCalledWith(
      expect.objectContaining({ contract: "sale", featured: true }),
    );
  });

  it("switches the catalog to rentals", async () => {
    mockedApi.property.search.mockResolvedValue(page([]));
    await renderWithProviders(<Home />);

    await fireEvent.press(screen.getByText("Affitta"));

    await waitFor(() =>
      expect(mockedApi.property.search).toHaveBeenCalledWith(
        expect.objectContaining({ contract: "rent", featured: true }),
      ),
    );
  });
});

describe("Property detail", () => {
  it("shows price and features and opens WhatsApp with the reference", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail());
    const openURL = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
    await renderWithProviders(<PropertyScreen />);

    expect(await screen.findByText("139.000 €")).toBeTruthy();
    expect(screen.getByText("Balcone")).toBeTruthy();
    await fireEvent.press(screen.getByText("WhatsApp"));

    expect(openURL).toHaveBeenCalledWith(expect.stringContaining("TR00001"));
  });

  it("saves the property in the favorites on the device", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail());
    await renderWithProviders(<PropertyScreen />);

    await fireEvent.press(await screen.findByLabelText("Aggiungi ai preferiti"));

    await waitFor(async () => expect(await AsyncStorage.getItem(FAVORITES_KEY)).toBe('["p1"]'));
    expect(screen.getByLabelText("Togli dai preferiti")).toBeTruthy();
  });

  it("explains when the property is no longer available", async () => {
    mockedApi.property.getPublic.mockRejectedValue(
      new ApiError(404, { code: "not_found", message: "", details: {} }),
    );

    await renderWithProviders(<PropertyScreen />);

    expect(await screen.findByText("Questo immobile non è più disponibile.")).toBeTruthy();
  });
});

describe("Favorites", () => {
  it("works without registration and lists saved properties", async () => {
    await AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(["p1"]));
    mockedApi.property.getPublic.mockResolvedValue(makeDetail());

    await renderWithProviders(<Favorites />);

    expect(await screen.findByText("Trilocale luminoso con balcone")).toBeTruthy();
  });

  it("shows the empty state", async () => {
    await renderWithProviders(<Favorites />);

    expect(await screen.findByText("Non hai ancora salvato immobili.")).toBeTruthy();
  });
});

describe("Sell form", () => {
  it("does not send without consent and phone", async () => {
    await renderWithProviders(<Sell />);

    await fireEvent.press(screen.getByText("Richiedi di essere ricontattato"));

    expect(await screen.findByText("Serve il consenso per poterti ricontattare")).toBeTruthy();
    expect(mockedApi.lead.createOwnerRequest).not.toHaveBeenCalled();
  });

  it("sends the owner request and thanks the owner", async () => {
    mockedApi.lead.createOwnerRequest.mockResolvedValue({ id: "l1", kind: "rent", created_at: "" });
    await renderWithProviders(<Sell />);

    await fireEvent.press(screen.getByText("Affittare"));
    await fireEvent.changeText(screen.getByLabelText("Nome e cognome"), "Anna Bianchi");
    await fireEvent.changeText(screen.getByLabelText("Telefono"), "333 111 2222");
    await fireEvent.press(screen.getByText("Ho già deciso"));
    await fireEvent.press(
      screen.getByText("Ho letto l'informativa privacy e accetto di essere ricontattato"),
    );
    await fireEvent.press(screen.getByText("Richiedi di essere ricontattato"));

    expect(await screen.findByText("Grazie, richiesta inviata!")).toBeTruthy();
    expect(mockedApi.lead.createOwnerRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "rent",
        full_name: "Anna Bianchi",
        intention: "decided",
        consent: expect.objectContaining({ privacy_accepted: true }),
      }),
    );
  });
});
