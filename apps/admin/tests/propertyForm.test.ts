import {
  EMPTY_FORM,
  formFromProperty,
  payloadFromForm,
  validateForm,
} from "../src/pages/propertyForm";
import { makeProperty } from "./helpers";

describe("payloadFromForm", () => {
  it("converts numbers and turns empty fields into null", () => {
    const payload = payloadFromForm({
      ...EMPTY_FORM,
      title: "  Villa con giardino ",
      price: "250000",
      surface_sqm: "180",
      rooms: "",
      zone: " ",
      latitude: "42,35",
      longitude: "14.16",
    });

    expect(payload).toMatchObject({
      title: "Villa con giardino",
      price: 250000,
      surface_sqm: 180,
      rooms: null,
      zone: null,
      latitude: "42.35",
      longitude: "14.16",
    });
  });

  it("drops rental fields for sales", () => {
    const payload = payloadFromForm({
      ...EMPTY_FORM,
      contract: "sale",
      tenant_types: ["students"],
      accommodation: "single_room",
      available_from: "2026-11-01",
    });

    expect(payload).toMatchObject({ tenant_types: [], accommodation: null, available_from: null });
  });

  it("keeps rental fields for rentals", () => {
    const payload = payloadFromForm({
      ...EMPTY_FORM,
      contract: "rent",
      tenant_types: ["students", "workers"],
      accommodation: "single_room",
      available_from: "2026-11-01",
    });

    expect(payload).toMatchObject({
      tenant_types: ["students", "workers"],
      accommodation: "single_room",
      available_from: "2026-11-01",
    });
  });
});

describe("validateForm", () => {
  it("reports the missing required fields", () => {
    const errors = validateForm({ ...EMPTY_FORM, municipality: "" });

    expect(Object.keys(errors).sort()).toEqual(["municipality", "price", "surface_sqm", "title"]);
  });

  it("requires both coordinates", () => {
    const errors = validateForm({
      ...EMPTY_FORM,
      title: "Trilocale",
      price: "1",
      surface_sqm: "1",
      latitude: "42.3",
    });

    expect(errors).toEqual({ longitude: expect.any(String) });
  });
});

describe("formFromProperty", () => {
  it("round-trips through the payload", () => {
    const property = makeProperty({ rooms: 3, zone: "Centro", features: ["garden"] });

    const payload = payloadFromForm(formFromProperty(property));

    expect(payload).toMatchObject({ rooms: 3, zone: "Centro", features: ["garden"], floor: null });
  });
});
