import type { Place, ValuationCreated } from "@taraborrelli/api-client";
import { fireEvent, screen } from "@testing-library/react-native";
import { Linking } from "react-native";

import EstimateWizard from "../app/stima";
import Sell from "../app/(tabs)/vendi";
import { router } from "expo-router";

import { api } from "../src/api";
import {
  EMPTY_VALUATION,
  isAnswered,
  stepErrors,
  stepsFor,
  toValuationRequest,
  type ValuationForm,
} from "../src/valuation";
import { renderWithProviders } from "./helpers";

jest.mock("../src/api", () => ({
  api: { lead: { geocode: jest.fn(), createValuation: jest.fn(), createOwnerRequest: jest.fn() } },
}));

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), back: jest.fn(), replace: jest.fn(), canGoBack: () => true },
}));

const mockedApi = api as unknown as { lead: { geocode: jest.Mock; createValuation: jest.Mock } };

const PLACE: Place = {
  label: "Via di Prova 1, Chieti",
  latitude: 42.35,
  longitude: 14.16,
  municipality: "Chieti",
  road: "Via di Prova",
  house_number: "1",
  postcode: "66100",
};

const CREATED: ValuationCreated = {
  id: "l1",
  kind: "valuation",
  created_at: "2026-10-30T09:00:00Z",
  completion_token: "secret",
  completion_expires_at: "2026-11-06T09:00:00Z",
  estimate: {
    min_value: 110000,
    max_value: 150000,
    min_per_sqm: 1100,
    max_per_sqm: 1500,
    municipality: "Chieti",
    zone_code: "B1",
    zone_description: "CENTRO STORICO",
    semester: "2026/1",
    source: "OMI - Agenzia delle Entrate",
  },
  estimate_unavailable: null,
};

function filled(overrides: Partial<ValuationForm> = {}): ValuationForm {
  return {
    ...EMPTY_VALUATION,
    place: PLACE,
    latitude: 42.351,
    longitude: 14.161,
    homeType: "apartment",
    category: "A2",
    surface: "95",
    rooms: "4",
    floor: 2,
    hasElevator: true,
    condition: "good",
    works: "yes",
    intention: "planning",
    fullName: "Anna Bianchi",
    phone: "333 111 2222",
    privacyAccepted: true,
    ...overrides,
  };
}

beforeEach(() => jest.clearAllMocks());

describe("valuation steps", () => {
  it("asks the floor only for apartments and attics", () => {
    expect(stepsFor(filled())).toContain("floor");
    expect(stepsFor(filled({ homeType: "villa" }))).not.toContain("floor");
  });

  it("needs an answer before going on", () => {
    expect(isAnswered("type", EMPTY_VALUATION)).toBe(false);
    expect(isAnswered("type", filled())).toBe(true);
    expect(isAnswered("floor", filled({ hasElevator: null }))).toBe(false);
  });

  it("checks surface, rooms and contacts like the service", () => {
    expect(stepErrors("size", filled({ surface: "5", rooms: "40" }))).toEqual({
      surface: "Inserisci una superficie tra 10 e 5.000 m²",
      rooms: "Inserisci un numero di locali tra 1 e 30",
    });
    expect(
      Object.keys(stepErrors("contacts", filled({ phone: "12", privacyAccepted: false }))),
    ).toEqual(["phone", "privacy"]);
  });

  it("sends the moved pin position, the answers and the consent", () => {
    const request = toValuationRequest(filled());

    expect(request).toMatchObject({
      municipality: "Chieti",
      property_type: "apartment",
      surface_sqm: 95,
      rooms: 4,
      address: "Via di Prova 1, Chieti",
      latitude: 42.351,
      longitude: 14.161,
      cadastral_category: "A2",
      building_works: "yes",
      floor: 2,
      has_elevator: true,
      consent: { privacy_accepted: true, privacy_policy_version: "2026-01" },
    });
  });

  it("does not send floor and elevator for a villa", () => {
    const request = toValuationRequest(filled({ homeType: "villa" }));

    expect(request.floor).toBeNull();
    expect(request.has_elevator).toBeNull();
  });
});

async function next() {
  await fireEvent.press(screen.getByText("Avanti"));
}

async function choose(label: string) {
  await fireEvent.press(screen.getByText(label));
}

describe("estimate wizard", () => {
  it("opens from the Vendi casa screen", async () => {
    await renderWithProviders(<Sell />);

    await fireEvent.press(screen.getByText("Calcola la stima"));

    expect(router.push).toHaveBeenCalledWith("/stima");
  });

  it("searches the address only when asked and shows the map", async () => {
    mockedApi.lead.geocode.mockResolvedValue({ items: [PLACE], total: 1, page: 1, size: 1 });
    await renderWithProviders(<EstimateWizard />);

    await fireEvent.changeText(screen.getByLabelText("Indirizzo"), "via di prova 1 chieti");
    expect(mockedApi.lead.geocode).not.toHaveBeenCalled();
    await fireEvent.press(screen.getByText("Cerca"));
    await fireEvent.press(await screen.findByText("Via di Prova 1, Chieti"));

    expect(mockedApi.lead.geocode).toHaveBeenCalledWith("via di prova 1 chieti");
    expect(screen.getByLabelText("Mappa con la posizione della casa")).toBeTruthy();
    expect(screen.getByText("Passo 1 di 8")).toBeTruthy();
  });

  it("explains when the address search is not available", async () => {
    mockedApi.lead.geocode.mockRejectedValue(new Error("down"));
    await renderWithProviders(<EstimateWizard />);

    await fireEvent.changeText(screen.getByLabelText("Indirizzo"), "via di prova");
    await fireEvent.press(screen.getByText("Cerca"));

    expect(await screen.findByText(/ricerca dell'indirizzo non è disponibile/)).toBeTruthy();
  });

  it("goes through the questions and shows the indicative range", async () => {
    mockedApi.lead.geocode.mockResolvedValue({ items: [PLACE], total: 1, page: 1, size: 1 });
    mockedApi.lead.createValuation.mockResolvedValue(CREATED);
    await renderWithProviders(<EstimateWizard />);

    await fireEvent.changeText(screen.getByLabelText("Indirizzo"), "via di prova 1 chieti");
    await fireEvent.press(screen.getByText("Cerca"));
    await fireEvent.press(await screen.findByText("Via di Prova 1, Chieti"));
    await next();
    await choose("Appartamento");
    await next();
    await choose("A/2 – Civile");
    await next();
    await fireEvent.changeText(screen.getByLabelText("Superficie (m²)"), "95");
    await fireEvent.changeText(screen.getByLabelText("Locali"), "4");
    await next();
    await choose("2°");
    await choose("Sì");
    await next();
    await choose("Buono, abitabile");
    await next();
    await choose("No");
    await next();
    await choose("Ci sto pensando per i prossimi mesi");
    await next();
    expect(screen.getByLabelText("Nome e cognome").props.value).toBe("Anna Bianchi");
    await fireEvent.changeText(screen.getByLabelText("Telefono"), "333 111 2222");
    await choose("Ho letto l'informativa privacy e accetto di essere ricontattato");
    await fireEvent.press(screen.getByText("Calcola la stima"));

    expect(await screen.findByText("Tra 110.000 € e 150.000 €")).toBeTruthy();
    expect(
      screen.getByText(/1\.100 – 1\.500 €\/m² · Zona OMI B1 \(centro storico\), Chieti/),
    ).toBeTruthy();
    expect(screen.getByText(/non è una valutazione professionale/)).toBeTruthy();
    expect(mockedApi.lead.createValuation).toHaveBeenCalledWith(
      expect.objectContaining({
        cadastral_category: "A2",
        floor: 2,
        has_elevator: true,
        building_works: "no",
        intention: "planning",
        latitude: 42.35,
      }),
    );
  });

  it("keeps Avanti disabled until the question is answered", async () => {
    await renderWithProviders(<EstimateWizard />);

    expect(screen.getByText("Avanti")).toBeTruthy();
    const button = screen.getByRole("button", { name: "Avanti" });
    expect(button.props.accessibilityState.disabled).toBe(true);
  });

  it("without an estimate still confirms the request and offers a call", async () => {
    const openURL = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
    mockedApi.lead.geocode.mockResolvedValue({ items: [PLACE], total: 1, page: 1, size: 1 });
    mockedApi.lead.createValuation.mockResolvedValue({
      ...CREATED,
      estimate: null,
      estimate_unavailable: "outside_zones",
    });
    await renderWithProviders(<EstimateWizard />);

    await fireEvent.changeText(screen.getByLabelText("Indirizzo"), "via di prova 1 chieti");
    await fireEvent.press(screen.getByText("Cerca"));
    await fireEvent.press(await screen.findByText("Via di Prova 1, Chieti"));
    await next();
    await choose("Villa");
    await next();
    await choose("Non lo so");
    await next();
    await fireEvent.changeText(screen.getByLabelText("Superficie (m²)"), "200");
    await fireEvent.changeText(screen.getByLabelText("Locali"), "7");
    await next();
    await choose("Da ristrutturare");
    await next();
    await choose("Non lo so");
    await next();
    await choose("Voglio solo sapere quanto vale");
    await next();
    await fireEvent.changeText(screen.getByLabelText("Telefono"), "333 111 2222");
    await choose("Ho letto l'informativa privacy e accetto di essere ricontattato");
    await fireEvent.press(screen.getByText("Calcola la stima"));

    expect(await screen.findByText("Richiesta ricevuta")).toBeTruthy();
    expect(screen.getByText(/non abbiamo ancora i valori di riferimento/)).toBeTruthy();
    await fireEvent.press(screen.getByText("Chiamaci ora"));
    expect(openURL).toHaveBeenCalledWith(expect.stringMatching(/^tel:/));
  });
});
