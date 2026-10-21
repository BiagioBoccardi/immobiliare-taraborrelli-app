import { ApiError, type ImportPreview } from "@taraborrelli/api-client";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { issueText } from "../src/pages/ImportPage";
import { fakeApi, page, renderApp, signedInStore } from "./helpers";

function preview(overrides: Partial<ImportPreview> = {}): ImportPreview {
  return {
    columns: [
      { header: "Rif.", field: "external_ref" },
      { header: "Ascensore", field: "features.elevator" },
    ],
    ignored_columns: ["Note interne"],
    missing_columns: [],
    rows: [
      {
        row: 2,
        action: "create",
        external_ref: "RS-1",
        title: "Trilocale luminoso",
        municipality: "Chieti",
        contract: "sale",
        price: 139000,
        errors: [],
        warnings: [],
      },
      {
        row: 3,
        action: "invalid",
        external_ref: "RS-2",
        title: "Villa",
        municipality: "Chieti",
        contract: "sale",
        price: null,
        errors: [{ code: "invalid_number", column: "Prezzo", field: "price", value: "boh" }],
        warnings: [],
      },
      {
        row: 4,
        action: "update",
        external_ref: "RS-3",
        title: "Attico",
        municipality: "Chieti",
        contract: "sale",
        price: 1000,
        errors: [],
        warnings: [{ code: "price_unusual_sale", column: null, field: "price", value: null }],
      },
    ],
    totals: { create: 1, update: 1, invalid: 1 },
    ...overrides,
  };
}

const xlsx = () =>
  new File(["contenuto"], "export.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });

async function chooseAndCheck(api: ReturnType<typeof fakeApi>) {
  renderApp(api, await signedInStore(api), "/properties/import");
  await userEvent.upload(await screen.findByLabelText("File Excel o CSV"), xlsx());
  await userEvent.click(screen.getByRole("button", { name: "Controlla il file" }));
}

describe("Excel import", () => {
  it("is reachable from the properties page", async () => {
    const api = fakeApi();
    api.property.list.mockResolvedValue(page([]));
    renderApp(api, await signedInStore(api), "/properties");

    await userEvent.click(await screen.findByRole("link", { name: "Importa da Excel" }));

    expect(await screen.findByRole("heading", { name: "Importa immobili da Excel" })).toBeVisible();
  });

  it("checks the file and shows what will be created, updated and skipped", async () => {
    const api = fakeApi();
    api.property.previewImport.mockResolvedValue(preview());

    await chooseAndCheck(api);

    expect(await screen.findByText("1 nuovi")).toBeVisible();
    expect(screen.getByText("1 da aggiornare")).toBeVisible();
    expect(screen.getByText("1 non importabili")).toBeVisible();
    expect(screen.getByText("«boh» non è un numero valido (Prezzo).")).toBeVisible();
    expect(screen.getByText("Rif. → Codice nel gestionale (Reasoft)")).toBeVisible();
    expect(screen.getByText("Ascensore → Dotazione: Ascensore")).toBeVisible();
    expect(screen.getByText("Note interne")).toBeVisible();
    expect(api.property.runImport).not.toHaveBeenCalled();
  });

  it("filters the rows with problems", async () => {
    const api = fakeApi();
    api.property.previewImport.mockResolvedValue(preview());
    await chooseAndCheck(api);

    await userEvent.click(await screen.findByLabelText("Mostra solo le righe con avvisi o errori"));

    const table = screen.getByRole("table");
    expect(within(table).queryByText("RS-1")).not.toBeInTheDocument();
    expect(within(table).getByText("RS-2")).toBeVisible();
    expect(within(table).getByText("RS-3")).toBeVisible();
  });

  it("imports the valid rows of the same file and reports the result", async () => {
    const api = fakeApi();
    api.property.previewImport.mockResolvedValue(preview());
    api.property.runImport.mockResolvedValue({ created: 1, updated: 1, skipped: 1 });
    await chooseAndCheck(api);

    await userEvent.click(await screen.findByRole("button", { name: "Importa 2 immobili" }));

    expect(
      await screen.findByText("Importazione completata: 1 nuovi, 1 aggiornati, 1 righe saltate."),
    ).toBeVisible();
    expect(api.property.runImport).toHaveBeenCalledWith(expect.any(File));
    expect(screen.getByRole("link", { name: "Vai agli immobili in bozza" })).toBeVisible();
  });

  it("does not offer the import when no row is valid", async () => {
    const api = fakeApi();
    api.property.previewImport.mockResolvedValue(
      preview({ totals: { create: 0, update: 0, invalid: 3 } }),
    );

    await chooseAndCheck(api);

    expect(
      await screen.findByText(
        "Nessuna riga può essere importata: correggi il file e ricontrollalo.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /^Importa \d/ })).not.toBeInTheDocument();
  });

  it("warns about missing required columns", async () => {
    const api = fakeApi();
    api.property.previewImport.mockResolvedValue(
      preview({ missing_columns: ["price", "surface_sqm"] }),
    );

    await chooseAndCheck(api);

    expect(await screen.findByRole("alert")).toHaveTextContent("Prezzo (€), Superficie (m²)");
  });

  it("explains an old .xls file", async () => {
    const api = fakeApi();
    api.property.previewImport.mockRejectedValue(
      new ApiError(400, { code: "xls_not_supported", message: "", details: {} }),
    );

    await chooseAndCheck(api);

    expect(
      await screen.findByText(
        "Il formato .xls non è supportato: apri il file in Excel e salvalo come .xlsx.",
      ),
    ).toBeVisible();
  });

  it("keeps the check button disabled until a file is chosen", async () => {
    const api = fakeApi();
    renderApp(api, await signedInStore(api), "/properties/import");

    expect(await screen.findByRole("button", { name: "Controlla il file" })).toBeDisabled();
  });
});

describe("issueText", () => {
  it("falls back to a generic message for unknown codes", () => {
    expect(issueText({ code: "something_new", column: null, field: "zone", value: null })).toBe(
      "Dato da verificare: «Zona o quartiere».",
    );
  });
});
