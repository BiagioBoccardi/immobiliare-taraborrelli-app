import { ApiError } from "@taraborrelli/api-client";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { fakeApi, makeProperty, page, renderApp, signedInStore } from "./helpers";

const draft = makeProperty({ id: "p1", reference: "TR00001", status: "draft" });
const published = makeProperty({ id: "p2", reference: "TR00002", status: "published" });

async function openList(api: ReturnType<typeof fakeApi>, path = "/properties") {
  api.property.list.mockResolvedValue(page([draft, published]));
  renderApp(api, await signedInStore(api), path);
  await screen.findByText("TR00001");
}

describe("actions on each property", () => {
  it("publishes a draft from the list", async () => {
    const api = fakeApi();
    api.property.changeStatus.mockResolvedValue({ ...draft, status: "published" });
    await openList(api);

    await userEvent.click(screen.getByRole("button", { name: "Pubblica TR00001" }));

    expect(await screen.findByText("Immobile TR00001 pubblicato.")).toBeVisible();
    expect(api.property.changeStatus).toHaveBeenCalledWith("p1", "published");
    expect(screen.queryByRole("button", { name: "Pubblica TR00002" })).not.toBeInTheDocument();
  });

  it("explains why a draft cannot be published", async () => {
    const api = fakeApi();
    api.property.changeStatus.mockRejectedValue(
      new ApiError(409, { code: "photo_required", message: "", details: {} }),
    );
    await openList(api);

    await userEvent.click(screen.getByRole("button", { name: "Pubblica TR00001" }));

    expect(
      await screen.findByText("Serve almeno una foto per pubblicare l'immobile."),
    ).toBeVisible();
  });

  it("opens the property to edit it", async () => {
    const api = fakeApi();
    api.property.get.mockResolvedValue(published);
    await openList(api);

    await userEvent.click(screen.getByRole("link", { name: "Modifica TR00002" }));

    expect(await screen.findByLabelText("Titolo dell'annuncio")).toBeVisible();
  });

  it("deletes any property after confirmation", async () => {
    const api = fakeApi();
    api.property.remove.mockResolvedValue(undefined);
    await openList(api);

    await userEvent.click(screen.getByRole("button", { name: "Elimina TR00002" }));
    expect(api.property.remove).not.toHaveBeenCalled();
    await userEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "Elimina" }),
    );

    expect(await screen.findByText("Immobile TR00002 eliminato.")).toBeVisible();
    expect(api.property.remove).toHaveBeenCalledWith("p2");
  });
});

describe("actions on all the properties shown", () => {
  it("publishes all with the current filters and explains the skipped ones", async () => {
    const api = fakeApi();
    api.property.bulkPublish.mockResolvedValue({
      done: 1,
      skipped: [
        { id: "a", reference: "TR00003", title: "A", reason: "photo_required" },
        { id: "b", reference: "TR00004", title: "B", reason: "photo_required" },
        { id: "c", reference: "TR00005", title: "C", reason: "surface_required" },
      ],
    });
    await openList(api, "/properties?status=draft");

    await userEvent.click(screen.getByRole("button", { name: "Pubblica tutti" }));
    await userEvent.click(
      within(screen.getByRole("alertdialog")).getByRole("button", { name: "Pubblica tutti" }),
    );

    expect(await screen.findByText("Pubblicati 1 immobili.")).toBeVisible();
    expect(screen.getByText("Non pubblicati: 3 (2 senza foto, 1 senza superficie).")).toBeVisible();
    expect(api.property.bulkPublish).toHaveBeenCalledWith(
      expect.objectContaining({ status: "draft" }),
    );
  });

  it("deletes all only after confirmation", async () => {
    const api = fakeApi();
    api.property.bulkDelete.mockResolvedValue({ done: 2, skipped: [] });
    await openList(api);

    await userEvent.click(screen.getByRole("button", { name: "Elimina tutti" }));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText("Eliminare gli immobili mostrati (2)?")).toBeVisible();
    await userEvent.click(within(dialog).getByRole("button", { name: "Elimina" }));

    expect(await screen.findByText("Eliminati 2 immobili.")).toBeVisible();
    expect(api.property.bulkDelete).toHaveBeenCalledTimes(1);
  });

  it("cancelling the confirmation changes nothing", async () => {
    const api = fakeApi();
    await openList(api);

    await userEvent.click(screen.getByRole("button", { name: "Elimina tutti" }));
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(api.property.bulkDelete).not.toHaveBeenCalled();
  });
});

describe("management software code", () => {
  it("shows the Reasoft code as reference and names the actions after it", async () => {
    const api = fakeApi();
    const imported = makeProperty({ id: "p3", reference: "TR00003", external_ref: "75" });
    api.property.list.mockResolvedValue(page([imported, draft]));
    renderApp(api, await signedInStore(api), "/properties");

    expect(await screen.findByText("75")).toBeVisible();
    expect(screen.queryByText("TR00003")).not.toBeInTheDocument();
    expect(screen.getByText("TR00001")).toBeVisible();
    expect(screen.getByRole("link", { name: "Modifica 75" })).toBeVisible();
  });
});
