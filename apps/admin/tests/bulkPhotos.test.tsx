import { ApiError } from "@taraborrelli/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { findCode, normalizeCode, planBulkPhotos } from "../src/pages/bulkPhotos";
import { fakeApi, makeProperty, page, renderApp, signedInStore } from "./helpers";

function photo(path: string, type = "image/jpeg"): File {
  const name = path.split("/").pop() ?? path;
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "webkitRelativePath", { value: path.includes("/") ? path : "" });
  return file;
}

const villa = makeProperty({ id: "p88", reference: "TR00001", external_ref: "88", photos: [] });
const flat = makeProperty({ id: "p87", reference: "TR00002", external_ref: "RS-87", photos: [] });

describe("matching photos with the management code", () => {
  it("treats 088 and 88 as the same code", () => {
    expect(normalizeCode("088")).toBe("88");
    expect(normalizeCode(" RS-87 ")).toBe("rs-87");
  });

  it.each([
    ["foto/88/1.jpg", "88"],
    ["foto/88 - Villa Oliveti/cucina.jpg", "88"],
    ["88_1.jpg", "88"],
    ["088-2.jpg", "88"],
    ["88 (3).jpg", "88"],
    ["RS-87_1.jpg", "rs-87"],
    ["foto/altro/RS-87.jpg", "rs-87"],
  ])("finds the code in %s", (path, code) => {
    expect(findCode(path, new Set(["88", "rs-87"]))).toBe(code);
  });

  it("returns null when no code matches", () => {
    expect(findCode("vacanze/mare.jpg", new Set(["88"]))).toBeNull();
  });

  it("groups photos by property in name order and lists the unmatched ones", () => {
    const plan = planBulkPhotos(
      [
        photo("foto/88/10.jpg"),
        photo("foto/88/2.jpg"),
        photo("foto/99/1.jpg"),
        photo("foto/88/ritratto.heic", "image/heic"),
        photo("foto/.DS_Store", ""),
        photo("RS-87_1.png", "image/png"),
      ],
      [villa, flat],
      true,
    );

    expect(plan.groups.map((g) => [g.property.id, g.files.map((f) => f.name)])).toEqual([
      ["p88", ["2.jpg", "10.jpg"]],
      ["p87", ["RS-87_1.png"]],
    ]);
    expect(plan.unmatched).toEqual([
      { path: "foto/99/1.jpg", reason: "no_property" },
      { path: "foto/88/ritratto.heic", reason: "unsupported_type" },
    ]);
  });

  it("skips properties that already have photos when asked", () => {
    const withPhotos = makeProperty({
      id: "p1",
      external_ref: "1",
      photos: [
        {
          id: "f",
          url: "u",
          caption: null,
          position: 0,
          show_when_sold: false,
          content_type: "image/jpeg",
          size_bytes: 1,
        },
      ],
    });

    const [skip] = planBulkPhotos([photo("1_a.jpg")], [withPhotos], true).groups;
    const [add] = planBulkPhotos([photo("1_a.jpg")], [withPhotos], false).groups;

    expect(skip?.skipped).toBe(true);
    expect(add?.skipped).toBe(false);
  });

  it("leaves out the photos beyond 40 per property", () => {
    const files = Array.from({ length: 45 }, (_, i) => photo(`88_${i + 1}.jpg`));

    const [group] = planBulkPhotos(files, [villa], true).groups;

    expect(group?.files).toHaveLength(40);
    expect(group?.overLimit).toBe(5);
  });
});

describe("bulk photo page", () => {
  it("shows the matches and uploads every photo to its property", async () => {
    const api = fakeApi();
    api.property.list.mockResolvedValue(page([villa, flat]));
    api.property.uploadPhoto.mockResolvedValue(villa);
    renderApp(api, await signedInStore(api), "/properties/photos");

    await userEvent.upload(await screen.findByLabelText("Oppure scegli le singole foto"), [
      photo("88_1.jpg"),
      photo("88_2.jpg"),
      photo("RS-87_1.jpg"),
    ]);
    expect(await screen.findByText("3 foto per 2 immobili")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Carica 3 foto" }));

    expect(await screen.findByText("Caricamento completato: 3 foto caricate.")).toBeVisible();
    expect(api.property.uploadPhoto).toHaveBeenCalledTimes(3);
    expect(api.property.uploadPhoto.mock.calls.map((call) => call[0]).sort()).toEqual([
      "p87",
      "p88",
      "p88",
    ]);
  });

  it("reports the photos the server refused", async () => {
    const api = fakeApi();
    api.property.list.mockResolvedValue(page([villa]));
    api.property.uploadPhoto.mockRejectedValue(
      new ApiError(400, { code: "invalid_photo", message: "", details: {} }),
    );
    renderApp(api, await signedInStore(api), "/properties/photos");

    await userEvent.upload(await screen.findByLabelText("Oppure scegli le singole foto"), [
      photo("88_1.jpg"),
    ]);
    await userEvent.click(await screen.findByRole("button", { name: "Carica 1 foto" }));

    const alert = await screen.findByRole("alert");
    await waitFor(() => expect(alert).toHaveTextContent("1 foto non caricate"));
    expect(within(alert).getByText(/TR00001 · 88_1\.jpg/)).toBeVisible();
  });
});
