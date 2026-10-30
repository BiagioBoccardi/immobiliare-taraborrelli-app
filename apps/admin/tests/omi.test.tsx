import { ApiError, type OmiImportResult } from "@taraborrelli/api-client";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { fakeApi, makeLead, renderApp, signedInStore } from "./helpers";

const loaded = {
  semester: "2026/1",
  quotes: 120,
  zones: 18,
  municipalities: ["Chieti", "Francavilla Al Mare"],
  imported_at: "2026-10-30T09:00:00Z",
};

function file(name: string): File {
  return new File(["x"], name);
}

describe("OMI quotations page", () => {
  it("says that no quotation is loaded yet", async () => {
    const api = fakeApi();
    api.lead.currentOmi.mockRejectedValue(
      new ApiError(404, { code: "omi_not_loaded", message: "", details: {} }),
    );
    renderApp(api, await signedInStore(api), "/omi");

    expect(await screen.findByText(/Nessuna quotazione caricata/)).toBeVisible();
  });

  it("shows the data in use", async () => {
    const api = fakeApi();
    api.lead.currentOmi.mockResolvedValue(loaded);
    renderApp(api, await signedInStore(api), "/omi");

    expect(await screen.findByText("2026/1")).toBeVisible();
    expect(screen.getByText("Chieti, Francavilla Al Mare")).toBeVisible();
  });

  it("uploads the files and reports zones without perimeter", async () => {
    const api = fakeApi();
    const result: OmiImportResult = {
      ...loaded,
      warnings: [{ code: "zone_without_perimeter", count: 1, examples: ["Chieti R1"] }],
    };
    api.lead.currentOmi.mockResolvedValue(loaded);
    api.lead.importOmi.mockResolvedValue(result);
    renderApp(api, await signedInStore(api), "/omi");
    const quotes = file("QI_1_20261_VALORI.csv");
    const kmz = file("Provincia di CHIETI.kmz");

    await userEvent.upload(await screen.findByLabelText("Quotazioni (…_VALORI.csv)"), quotes);
    await userEvent.upload(screen.getByLabelText("Perimetri delle zone (.kmz o .kml)"), kmz);
    await userEvent.click(screen.getByRole("button", { name: "Carica quotazioni" }));

    expect(await screen.findByText(/semestre 2026\/1 caricate: 18 zone/)).toBeVisible();
    expect(screen.getByText(/1 zone hanno valori ma nessun perimetro.*Chieti R1/)).toBeVisible();
    expect(api.lead.importOmi).toHaveBeenCalledWith({
      quotes,
      zones: undefined,
      perimeters: [kmz],
    });
  });

  it("keeps the button disabled until quotations and perimeters are chosen", async () => {
    const api = fakeApi();
    api.lead.currentOmi.mockResolvedValue(loaded);
    renderApp(api, await signedInStore(api), "/omi");

    await userEvent.upload(
      await screen.findByLabelText("Quotazioni (…_VALORI.csv)"),
      file("valori.csv"),
    );

    expect(screen.getByRole("button", { name: "Carica quotazioni" })).toBeDisabled();
  });

  it("names the file that could not be read", async () => {
    const api = fakeApi();
    api.lead.currentOmi.mockResolvedValue(loaded);
    api.lead.importOmi.mockRejectedValue(
      new ApiError(422, {
        code: "omi_invalid_file",
        message: "",
        details: { file: "rotto.kmz" },
      }),
    );
    renderApp(api, await signedInStore(api), "/omi");

    await userEvent.upload(
      await screen.findByLabelText("Quotazioni (…_VALORI.csv)"),
      file("valori.csv"),
    );
    await userEvent.upload(
      screen.getByLabelText("Perimetri delle zone (.kmz o .kml)"),
      file("rotto.kmz"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Carica quotazioni" }));

    expect(await screen.findByText(/non è un file OMI/)).toBeVisible();
    expect(screen.getByText("File: rotto.kmz")).toBeVisible();
  });
});

describe("estimate in the lead detail", () => {
  it("shows the range the owner saw and the answers of the simulator", async () => {
    const api = fakeApi();
    api.lead.getLead.mockResolvedValue(
      makeLead({
        details: {
          address: "Via di Prova 1, Chieti",
          latitude: 42.35,
          longitude: 14.16,
          cadastral_category: "A2",
          building_works: "yes",
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
        },
      }),
    );
    renderApp(api, await signedInStore(api), "/leads/lead-1");

    expect(await screen.findByText("Stima online mostrata al proprietario")).toBeVisible();
    expect(screen.getByText(/110\.000\s€ – 150\.000\s€/)).toBeVisible();
    expect(screen.getByText(/1\.100 – 1\.500 €\/m²/)).toBeVisible();
    expect(screen.getByText(/Zona OMI B1 \(centro storico\) · Chieti/)).toBeVisible();
    expect(screen.getByText(/non è una valutazione professionale/)).toBeVisible();
    expect(screen.getByText("A/2 – civile")).toBeVisible();
    expect(screen.getByRole("link", { name: "Apri sulla mappa" })).toHaveAttribute(
      "href",
      expect.stringContaining("mlat=42.35&mlon=14.16"),
    );
    expect(screen.queryByText("latitude")).not.toBeInTheDocument();
  });
});

describe("estimate from the agency listings in the lead detail", () => {
  it("says it comes from the agency's listings", async () => {
    const api = fakeApi();
    api.lead.getLead.mockResolvedValue(
      makeLead({
        details: {
          estimate: {
            basis: "agency_listings",
            min_value: 87000,
            max_value: 123000,
            min_per_sqm: 920,
            max_per_sqm: 1288,
            municipality: "Chieti",
            zone_code: null,
            zone_description: null,
            semester: null,
            listings: 5,
            listings_scope: "municipality_type",
            source: "Immobili in vendita di Immobiliare Taraborrelli",
          },
        },
      }),
    );
    renderApp(api, await signedInStore(api), "/leads/lead-1");

    expect(await screen.findByText(/87\.000\s€ – 123\.000\s€/)).toBeVisible();
    expect(
      screen.getByText(/Confronto con 5 immobili in vendita dell'agenzia a Chieti/),
    ).toBeVisible();
    expect(screen.getByText(/Nessuna quotazione OMI per questo indirizzo/)).toBeVisible();
  });
});
