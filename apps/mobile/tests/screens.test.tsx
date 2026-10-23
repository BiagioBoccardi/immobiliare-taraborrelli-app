import AsyncStorage from "@react-native-async-storage/async-storage";
import { ApiError } from "@taraborrelli/api-client";
import { fireEvent, screen, waitFor } from "@testing-library/react-native";
import { Linking } from "react-native";

import Home from "../app/(tabs)/index";
import Favorites from "../app/(tabs)/preferiti";
import Sell from "../app/(tabs)/vendi";
import PropertyScreen from "../app/immobile/[id]";
import ThreeDModelScreen from "../app/modello-3d/[id]";
import Mortgage from "../app/mutuo";
import { router } from "expo-router";
import { api } from "../src/api";
import { favoritesKey } from "../src/favorites";
import { makeCard, makeDetail, page, renderWithProviders, TEST_USER } from "./helpers";

const FAVORITES_KEY = favoritesKey(TEST_USER.id);

jest.mock("../src/api", () => ({
  api: {
    property: { search: jest.fn(), getPublic: jest.fn() },
    lead: { createOwnerRequest: jest.fn() },
  },
}));

let mockParams: Record<string, string> = { id: "p1" };

jest.mock("expo-router", () => ({
  router: {
    push: jest.fn(),
    navigate: jest.fn(),
    back: jest.fn(),
    replace: jest.fn(),
    canGoBack: () => true,
  },
  useLocalSearchParams: () => mockParams,
}));

const mockedApi = api as unknown as {
  property: { search: jest.Mock; getPublic: jest.Mock };
  lead: { createOwnerRequest: jest.Mock };
};

beforeEach(async () => {
  jest.clearAllMocks();
  mockParams = { id: "p1" };
  await AsyncStorage.clear();
});

describe("Home", () => {
  it("greets the user by first name", async () => {
    mockedApi.property.search.mockResolvedValue(page([]));

    await renderWithProviders(<Home />);

    expect(screen.getByText("Ciao, Anna")).toBeTruthy();
  });

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

describe("Photo gallery", () => {
  const photos = [1, 2, 3].map((n) => ({
    id: `f${n}`,
    url: `https://media.test/f${n}.jpg`,
    caption: null,
  }));

  it("moves to the next and previous photo with the arrows", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail({ photos }));
    await renderWithProviders(<PropertyScreen />);

    expect(await screen.findByText("1/3")).toBeTruthy();
    expect(screen.queryByLabelText("Foto precedente")).toBeNull();
    await fireEvent.press(screen.getByLabelText("Foto successiva"));
    await fireEvent.press(screen.getByLabelText("Foto successiva"));

    expect(screen.getByText("3/3")).toBeTruthy();
    expect(screen.queryByLabelText("Foto successiva")).toBeNull();
    await fireEvent.press(screen.getByLabelText("Foto precedente"));
    expect(screen.getByText("2/3")).toBeTruthy();
  });

  it("jumps to a photo from its dot", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail({ photos }));
    await renderWithProviders(<PropertyScreen />);

    await fireEvent.press(await screen.findByRole("button", { name: "Foto 3 di 3" }));

    expect(screen.getByText("3/3")).toBeTruthy();
  });

  it("has no arrows with a single photo", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail());
    await renderWithProviders(<PropertyScreen />);

    expect(await screen.findByText("139.000 €")).toBeTruthy();
    expect(screen.queryByLabelText("Foto successiva")).toBeNull();
  });
});

describe("Property tools", () => {
  it("opens the mortgage calculator with the price of a property for sale", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail());
    await renderWithProviders(<PropertyScreen />);

    await fireEvent.press(await screen.findByText("Rata mutuo"));

    expect(router.push).toHaveBeenCalledWith({
      pathname: "/mutuo",
      params: { prezzo: "139000" },
    });
  });

  it("shows the 3D button only when the property has a model", async () => {
    mockedApi.property.getPublic.mockResolvedValue(
      makeDetail({ three_d_model: { url: "https://media.test/casa.glb", size_bytes: 1024 } }),
    );
    await renderWithProviders(<PropertyScreen />);

    await fireEvent.press(await screen.findByText("Vedi in 3D"));

    expect(router.push).toHaveBeenCalledWith("/modello-3d/p1");
  });

  it("does not offer 3D or mortgage for a rental without a model", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail({ contract: "rent", price: 500 }));
    await renderWithProviders(<PropertyScreen />);

    expect(await screen.findByText("500 €/mese")).toBeTruthy();
    expect(screen.queryByText("Vedi in 3D")).toBeNull();
    expect(screen.queryByText("Rata mutuo")).toBeNull();
  });
});

describe("3D model", () => {
  it("shows the viewer with the model of the property", async () => {
    mockedApi.property.getPublic.mockResolvedValue(
      makeDetail({ three_d_model: { url: "https://media.test/casa.glb", size_bytes: 1024 } }),
    );
    await renderWithProviders(<ThreeDModelScreen />);

    expect(await screen.findByLabelText("Trilocale luminoso con balcone")).toBeTruthy();
    expect(
      screen.getByText("Trascina per ruotare, pizzica o usa la rotellina per avvicinarti."),
    ).toBeTruthy();
  });

  it("explains when the property has no model", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail());
    await renderWithProviders(<ThreeDModelScreen />);

    expect(await screen.findByText("Questo immobile non ha ancora una vista 3D.")).toBeTruthy();
  });
});

describe("3D rooms", () => {
  const rooms = [1, 2, 3].map((n) => ({
    id: `f${n}`,
    url: `https://media.test/f${n}.jpg`,
    caption: null,
    three_d_url: n === 2 ? null : `https://media.test/f${n}.glb`,
  }));

  it("shows the rooms that have a 3D version and switches between them", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail({ photos: rooms }));
    await renderWithProviders(<ThreeDModelScreen />);

    expect((await screen.findAllByLabelText("Stanza 1")).length).toBeGreaterThan(0);
    expect(screen.getByText("1/2")).toBeTruthy();
    await fireEvent.press(screen.getByLabelText("Stanza successiva"));

    expect(screen.getByText("2/2")).toBeTruthy();
  });

  it("opens the room of the photo chosen in the gallery", async () => {
    mockParams = { id: "p1", foto: "f3" };
    mockedApi.property.getPublic.mockResolvedValue(makeDetail({ photos: rooms }));
    await renderWithProviders(<ThreeDModelScreen />);

    expect(await screen.findByText("2/2")).toBeTruthy();
  });

  it("offers the 3D of the current photo from the property gallery", async () => {
    mockedApi.property.getPublic.mockResolvedValue(makeDetail({ photos: rooms }));
    await renderWithProviders(<PropertyScreen />);

    await fireEvent.press(await screen.findByLabelText("Vedi questa stanza in 3D"));

    expect(router.push).toHaveBeenCalledWith({
      pathname: "/modello-3d/[id]",
      params: { id: "p1", foto: "f1" },
    });
  });
});

describe("Mortgage", () => {
  it("fills in the price of the property and shows the monthly payment", async () => {
    mockParams = { prezzo: "150000" };
    await renderWithProviders(<Mortgage />);

    expect(screen.getByDisplayValue("150.000")).toBeTruthy();
    expect(screen.getByDisplayValue("30.000")).toBeTruthy();
    // 120.000 € at 3% for 25 years.
    expect(screen.getByText("569 €")).toBeTruthy();
    expect(screen.getByText("Percentuale finanziata: 80% del prezzo")).toBeTruthy();
  });

  it("recalculates when the duration changes", async () => {
    mockParams = { prezzo: "150000" };
    await renderWithProviders(<Mortgage />);

    await fireEvent.press(screen.getByText("30 anni"));

    expect(screen.getByText("506 €")).toBeTruthy();
  });

  it("warns when the loan is above the usual 80%", async () => {
    mockParams = { prezzo: "150000" };
    await renderWithProviders(<Mortgage />);

    await fireEvent.changeText(screen.getByLabelText("Anticipo (€)"), "10.000");

    expect(screen.getByText(/fino all'80% del valore/)).toBeTruthy();
  });

  it("asks for a down payment lower than the price", async () => {
    mockParams = { prezzo: "150000" };
    await renderWithProviders(<Mortgage />);

    await fireEvent.changeText(screen.getByLabelText("Anticipo (€)"), "200.000");

    expect(screen.getByText("L'anticipo deve essere inferiore al prezzo")).toBeTruthy();
    expect(screen.queryByText("Rata mensile")).toBeNull();
  });

  it("always says that the result is indicative", async () => {
    mockParams = {};
    await renderWithProviders(<Mortgage />);

    expect(screen.getByText(/Il risultato è indicativo e non è un preventivo/)).toBeTruthy();
  });
});

describe("Favorites", () => {
  it("lists the properties saved by the user", async () => {
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

  it("fills in the name from the account", async () => {
    await renderWithProviders(<Sell />);

    expect(screen.getByLabelText("Nome e cognome").props.value).toBe("Anna Bianchi");
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
