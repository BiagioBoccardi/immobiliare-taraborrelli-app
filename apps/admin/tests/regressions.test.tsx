import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { fakeApi, makeLead, makeProperty, renderApp, signedInStore } from "./helpers";

// The server returns a new `updated_at` after every change: forms must not lose their state.

it("confirms the CRM save when the server returns a new updated_at", async () => {
  const api = fakeApi();
  const lead = makeLead();
  api.lead.getLead.mockResolvedValue(lead);
  api.lead.updateLead.mockResolvedValue({
    ...lead,
    status: "contacted",
    updated_at: "2026-10-13T10:00:00Z",
  });
  const store = await signedInStore(api);
  renderApp(api, store, "/leads/lead-1");

  await userEvent.selectOptions(await screen.findByLabelText("Stato"), "contacted");
  await userEvent.click(screen.getByRole("button", { name: "Salva" }));

  expect(await screen.findByText("Modifiche salvate")).toBeVisible();
});

it("keeps unsaved property edits when a photo is uploaded", async () => {
  const api = fakeApi();
  const property = makeProperty();
  api.property.get.mockResolvedValue(property);
  api.property.uploadPhoto.mockResolvedValue({
    ...property,
    updated_at: "2026-10-13T10:00:00Z",
    photos: [
      {
        id: "p1",
        url: "https://media.test/p1.jpg",
        caption: null,
        position: 0,
        show_when_sold: false,
        content_type: "image/jpeg",
        size_bytes: 10,
      },
    ],
  });
  const store = await signedInStore(api);
  renderApp(api, store, "/properties/prop-1");
  const title = await screen.findByLabelText("Titolo dell'annuncio");
  await userEvent.clear(title);
  await userEvent.type(title, "Titolo non ancora salvato");

  await userEvent.upload(
    screen.getByLabelText("Aggiungi foto"),
    new File(["a"], "facciata.jpg", { type: "image/jpeg" }),
  );

  await waitFor(() => expect(screen.getByText("Copertina")).toBeVisible());
  expect(screen.getByLabelText("Titolo dell'annuncio")).toHaveValue("Titolo non ancora salvato");
});
