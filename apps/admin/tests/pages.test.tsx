import { ApiError, type ApiClient } from "@taraborrelli/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SessionStore } from "../src/auth/session";
import {
  fakeApi,
  makeLead,
  makeProperty,
  makeUser,
  memoryStorage,
  page,
  renderApp,
  signedInStore,
} from "./helpers";

function anonymousStore(api: ReturnType<typeof fakeApi>): SessionStore {
  const store = new SessionStore(memoryStorage());
  store.attach(api as unknown as ApiClient);
  store.onSessionExpired();
  return store;
}

const apiError = (status: number, code: string) =>
  new ApiError(status, { code, message: code, details: {} });

describe("access", () => {
  it("sends anonymous visitors to the login page", async () => {
    const api = fakeApi();

    renderApp(api, anonymousStore(api), "/leads");

    expect(await screen.findByRole("heading", { name: "Accedi all'area gestione" })).toBeVisible();
  });

  it("logs in and shows an error for wrong credentials", async () => {
    const api = fakeApi();
    api.auth.login.mockRejectedValue(apiError(401, "invalid_credentials"));
    renderApp(api, anonymousStore(api), "/login");

    await userEvent.type(screen.getByLabelText("Email"), "laura@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "sbagliata");
    await userEvent.click(screen.getByRole("button", { name: "Accedi" }));

    expect(await screen.findByText("Email o password non corretti.")).toBeVisible();
  });

  it("hides the staff accounts page from non-admin staff", async () => {
    const api = fakeApi();
    api.lead.listLeads.mockResolvedValue(page([]));
    api.property.list.mockResolvedValue(page([]));
    const store = await signedInStore(api, makeUser({ role: "staff" }));

    renderApp(api, store, "/users");

    expect(await screen.findByRole("heading", { name: "Riepilogo" })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Account staff" })).not.toBeInTheDocument();
  });
});

describe("dashboard", () => {
  it("shows the counters that matter to the agency", async () => {
    const api = fakeApi();
    api.lead.listLeads.mockImplementation(
      async (filters: { status?: string; due_for_contact?: boolean }) =>
        filters.due_for_contact
          ? page([makeLead({ next_contact_at: "2026-10-12T08:00:00Z" })], 4)
          : page([], filters.status === "new" ? 7 : 0),
    );
    api.property.list.mockResolvedValue(page([], 12));
    const store = await signedInStore(api);

    renderApp(api, store, "/");

    const due = await screen.findByText("Da ricontattare");
    expect(await within(due.closest("a")!).findByText("4")).toBeVisible();
    expect(await screen.findByRole("link", { name: "Mario Rossi" })).toHaveAttribute(
      "href",
      "/leads/lead-1",
    );
  });
});

describe("leads", () => {
  it("lists leads and filters by status", async () => {
    const api = fakeApi();
    api.lead.listLeads.mockResolvedValue(page([makeLead()]));
    const store = await signedInStore(api);
    renderApp(api, store, "/leads");
    expect(await screen.findByText("Mario Rossi")).toBeVisible();

    await userEvent.selectOptions(screen.getByLabelText("Stato"), "contacted");

    await waitFor(() =>
      expect(api.lead.listLeads).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "contacted", page: 1 }),
      ),
    );
  });

  it("shows contact links and saves the CRM changes", async () => {
    const api = fakeApi();
    const lead = makeLead({ details: { sell_timeline: "within_3_months", has_garden: true } });
    api.lead.getLead.mockResolvedValue(lead);
    api.lead.updateLead.mockResolvedValue({ ...lead, status: "contacted" });
    const store = await signedInStore(api);
    renderApp(api, store, "/leads/lead-1");

    expect(await screen.findByRole("link", { name: "Chiama" })).toHaveAttribute(
      "href",
      "tel:+393330000000",
    );
    expect(screen.getByRole("link", { name: "WhatsApp" })).toHaveAttribute(
      "href",
      "https://wa.me/393330000000",
    );
    expect(screen.getByText("Entro 3 mesi")).toBeVisible();

    await userEvent.selectOptions(screen.getByLabelText("Stato"), "contacted");
    await userEvent.type(screen.getByLabelText("Note interne"), "Richiamare dopo le 18");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));

    await waitFor(() =>
      expect(api.lead.updateLead).toHaveBeenCalledWith("lead-1", {
        status: "contacted",
        priority: "high",
        next_contact_at: null,
        staff_notes: "Richiamare dopo le 18",
      }),
    );
  });

  it("shows a callback request from the website without the property section", async () => {
    const api = fakeApi();
    const lead = makeLead({
      kind: "callback",
      full_name: "Luca Neri",
      email: "luca.neri@example.com",
      intention: null,
      municipality: null,
      property_type: null,
      details: { preferred_time: "morning", source: "website" },
      message: "Cerco un bilocale a Chieti Scalo.",
    });
    api.lead.getLead.mockResolvedValue(lead);
    const store = await signedInStore(api);
    renderApp(api, store, "/leads/lead-1");

    expect(await screen.findByText(/Richiesta di ricontatto/)).toBeVisible();
    expect(screen.getByText("Mattina (9:00 – 12:00)")).toBeVisible();
    expect(screen.getByText("Sito web")).toBeVisible();
    expect(screen.getByText("Cerco un bilocale a Chieti Scalo.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Scrivi email" })).toHaveAttribute(
      "href",
      "mailto:luca.neri@example.com",
    );
    expect(screen.queryByRole("heading", { name: "Immobile" })).toBeNull();
  });

  it("deletes a lead only after confirmation", async () => {
    const api = fakeApi();
    api.lead.getLead.mockResolvedValue(makeLead());
    api.lead.deleteLead.mockResolvedValue(undefined);
    api.lead.listLeads.mockResolvedValue(page([]));
    const store = await signedInStore(api);
    renderApp(api, store, "/leads/lead-1");

    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));
    expect(api.lead.deleteLead).not.toHaveBeenCalled();
    const dialog = screen.getByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Elimina" }));

    await waitFor(() => expect(api.lead.deleteLead).toHaveBeenCalledWith("lead-1"));
    expect(await screen.findByRole("heading", { name: "Richieste proprietari" })).toBeVisible();
  });
});

describe("properties", () => {
  it("creates a draft and opens it", async () => {
    const api = fakeApi();
    const created = makeProperty({ id: "prop-9", title: "Villa con giardino" });
    api.property.create.mockResolvedValue(created);
    api.property.get.mockResolvedValue(created);
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/new");

    await userEvent.type(
      await screen.findByLabelText("Titolo dell'annuncio"),
      "Villa con giardino",
    );
    await userEvent.type(screen.getByLabelText("Prezzo (€)"), "250000");
    await userEvent.type(screen.getByLabelText("Superficie (m²)"), "180");
    await userEvent.click(screen.getByRole("checkbox", { name: "Giardino" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));

    await waitFor(() =>
      expect(api.property.create).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Villa con giardino",
          price: 250000,
          surface_sqm: 180,
          features: ["garden"],
          municipality: "Chieti",
        }),
      ),
    );
    expect(
      await screen.findByText("Immobile creato in bozza. Aggiungi le foto per pubblicarlo."),
    ).toBeVisible();
  });

  it("does not call the API when required fields are missing", async () => {
    const api = fakeApi();
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/new");

    await userEvent.click(await screen.findByRole("button", { name: "Salva" }));

    expect(screen.getAllByText("Campo obbligatorio").length).toBeGreaterThan(0);
    expect(api.property.create).not.toHaveBeenCalled();
  });

  it("shows rental fields only for rentals", async () => {
    const api = fakeApi();
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/new");
    expect(await screen.findByLabelText("Contratto")).toBeVisible();
    expect(screen.queryByText("Affitto per studenti e lavoratori")).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Contratto"), "rent");

    expect(screen.getByText("Affitto per studenti e lavoratori")).toBeVisible();
    expect(screen.getByLabelText("Canone mensile (€)")).toBeVisible();
  });

  it("offers only the allowed status changes and explains a refused publication", async () => {
    const api = fakeApi();
    api.property.get.mockResolvedValue(makeProperty({ status: "draft" }));
    api.property.changeStatus.mockRejectedValue(apiError(409, "photo_required"));
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/prop-1");

    const panel = (await screen.findByRole("heading", { name: "Stato e pubblicazione" })).closest(
      "section",
    )!;
    const buttons = within(panel)
      .getAllByRole("button")
      .map((button) => button.textContent);
    expect(buttons).toEqual(["Pubblicato", "Archiviato"]);

    await userEvent.click(within(panel).getByRole("button", { name: "Pubblicato" }));

    expect(
      await within(panel).findByText("Serve almeno una foto per pubblicare l'immobile."),
    ).toBeVisible();
  });

  it("rejects unsupported files before uploading", async () => {
    const api = fakeApi();
    api.property.get.mockResolvedValue(makeProperty());
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/prop-1");
    const input = await screen.findByLabelText("Aggiungi foto");

    await userEvent.upload(
      input,
      new File(["%PDF"], "planimetria.pdf", { type: "application/pdf" }),
      {
        applyAccept: false,
      },
    );

    expect(await screen.findByText("planimetria.pdf: formato non supportato.")).toBeVisible();
    expect(api.property.uploadPhoto).not.toHaveBeenCalled();
  });

  it("uploads valid photos one by one", async () => {
    const api = fakeApi();
    const property = makeProperty();
    api.property.get.mockResolvedValue(property);
    api.property.uploadPhoto.mockResolvedValue(property);
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/prop-1");
    const input = await screen.findByLabelText("Aggiungi foto");
    const files = [
      new File(["a"], "facciata.jpg", { type: "image/jpeg" }),
      new File(["b"], "cucina.png", { type: "image/png" }),
    ];

    await userEvent.upload(input, files);

    await waitFor(() => expect(api.property.uploadPhoto).toHaveBeenCalledTimes(2));
    expect(api.property.uploadPhoto.mock.calls.map((call) => (call[1] as File).name)).toEqual([
      "facciata.jpg",
      "cucina.png",
    ]);
  });

  it("uploads a 3D model", async () => {
    const api = fakeApi();
    const property = makeProperty();
    api.property.get.mockResolvedValue(property);
    api.property.uploadThreeDModel.mockResolvedValue({
      ...property,
      three_d_model: { url: "https://media.test/casa.glb", size_bytes: 3 * 1024 * 1024 },
    });
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/prop-1");
    const input = await screen.findByLabelText("Carica modello 3D");

    await userEvent.upload(input, new File(["glTF"], "casa.glb", { type: "model/gltf-binary" }), {
      applyAccept: false,
    });

    await waitFor(() => expect(api.property.uploadThreeDModel).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Modello caricato (3 MB)")).toBeVisible();
  });

  it("rejects a 3D model that is not a .glb file before uploading", async () => {
    const api = fakeApi();
    api.property.get.mockResolvedValue(makeProperty());
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/prop-1");
    const input = await screen.findByLabelText("Carica modello 3D");

    await userEvent.upload(input, new File(["obj"], "casa.obj", { type: "text/plain" }), {
      applyAccept: false,
    });

    expect(await screen.findByText("casa.obj: serve un file .glb.")).toBeVisible();
    expect(api.property.uploadThreeDModel).not.toHaveBeenCalled();
  });

  it("deletes the 3D model after confirmation", async () => {
    const api = fakeApi();
    const property = makeProperty({
      three_d_model: { url: "https://media.test/casa.glb", size_bytes: 1024 * 1024 },
    });
    api.property.get.mockResolvedValue(property);
    api.property.deleteThreeDModel.mockResolvedValue({ ...property, three_d_model: null });
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/prop-1");

    await userEvent.click(await screen.findByRole("button", { name: "Elimina modello" }));
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Elimina" }));

    await waitFor(() => expect(api.property.deleteThreeDModel).toHaveBeenCalledWith("prop-1"));
    expect(await screen.findByText("Nessun modello 3D per questo immobile.")).toBeVisible();
  });

  it("moves a photo to become the cover", async () => {
    const api = fakeApi();
    const photo = (id: string, position: number) => ({
      id,
      url: `https://media.test/${id}.jpg`,
      caption: null,
      position,
      show_when_sold: false,
      content_type: "image/jpeg",
      size_bytes: 10,
    });
    const property = makeProperty({ photos: [photo("a", 0), photo("b", 1)] });
    api.property.get.mockResolvedValue(property);
    api.property.reorderPhotos.mockResolvedValue(property);
    const store = await signedInStore(api);
    renderApp(api, store, "/properties/prop-1");

    const moveButtons = await screen.findAllByRole("button", { name: "Sposta prima" });
    await userEvent.click(moveButtons[1]!);

    await waitFor(() =>
      expect(api.property.reorderPhotos).toHaveBeenCalledWith("prop-1", ["b", "a"]),
    );
  });
});

describe("staff accounts", () => {
  it("lets an admin create a staff account", async () => {
    const api = fakeApi();
    api.auth.listUsers.mockResolvedValue(page([makeUser()]));
    api.auth.createStaff.mockResolvedValue(makeUser({ id: "user-2" }));
    const store = await signedInStore(api, makeUser({ id: "admin-1", role: "admin" }));
    renderApp(api, store, "/users");

    await userEvent.type(await screen.findByLabelText("Nome e cognome"), "Paolo Bianchi");
    await userEvent.type(screen.getByLabelText("Email"), "paolo@example.com");
    await userEvent.type(
      screen.getByLabelText("Password iniziale (almeno 10 caratteri)"),
      "Password-lunga-1",
    );
    await userEvent.click(screen.getByRole("button", { name: "Crea account" }));

    await waitFor(() =>
      expect(api.auth.createStaff).toHaveBeenCalledWith({
        full_name: "Paolo Bianchi",
        email: "paolo@example.com",
        password: "Password-lunga-1",
        role: "staff",
      }),
    );
    expect(await screen.findByText("Account creato.")).toBeVisible();
  });

  it("shows why the last admin cannot be demoted", async () => {
    const api = fakeApi();
    api.auth.listUsers.mockResolvedValue(page([makeUser({ id: "other", role: "admin" })]));
    api.auth.updateUser.mockRejectedValue(apiError(409, "last_admin"));
    const store = await signedInStore(api, makeUser({ id: "admin-1", role: "admin" }));
    renderApp(api, store, "/users");

    const table = await screen.findByRole("table");
    await userEvent.selectOptions(within(table).getByRole("combobox", { name: "Ruolo" }), "staff");

    expect(await screen.findByText("Deve restare almeno un amministratore attivo.")).toBeVisible();
  });
});
