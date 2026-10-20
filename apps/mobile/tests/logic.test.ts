import { formatEuro, formatPrice, place, whatsappUrl } from "../src/format";
import { tCount } from "../src/i18n";
import { gridFor, layoutFor, SIDEBAR_WIDTH } from "../src/layout";
import { toOwnerRequest, validateOwnerForm, EMPTY_OWNER_FORM } from "../src/ownerRequest";
import { activeFilterCount, DEFAULT_FILTERS, toQuery } from "../src/search";

describe("format", () => {
  it("formats prices in euro with dots", () => {
    expect(formatEuro(139000)).toBe("139.000 €");
    expect(formatEuro(1500)).toBe("1.500 €");
  });

  it("adds per month to rents", () => {
    expect(formatPrice(450, "rent")).toBe("450 €/mese");
    expect(formatPrice(450, "sale")).toBe("450 €");
  });

  it("puts the zone before the municipality", () => {
    expect(place("Chieti", "Centro")).toBe("Centro, Chieti");
    expect(place("Chieti", null)).toBe("Chieti");
  });

  it("builds a WhatsApp link with the encoded message", () => {
    expect(whatsappUrl("+39 333 000", "Rif. TR1 & più")).toBe(
      "https://wa.me/39333000?text=Rif.%20TR1%20%26%20pi%C3%B9",
    );
  });
});

describe("search filters", () => {
  it("drops empty filters from the query", () => {
    expect(toQuery(DEFAULT_FILTERS)).toEqual({
      contract: "sale",
      municipality: undefined,
      property_type: undefined,
      price_min: undefined,
      price_max: undefined,
      rooms_min: undefined,
      feature: undefined,
      tenant_type: undefined,
      sort: "newest",
    });
  });

  it("parses prices typed with dots and keeps tenant only for rentals", () => {
    const query = toQuery({
      ...DEFAULT_FILTERS,
      contract: "sale",
      priceMax: "150.000",
      tenantType: "students",
    });

    expect(query.price_max).toBe(150000);
    expect(query.tenant_type).toBeUndefined();
  });

  it("counts the active filters", () => {
    const count = activeFilterCount({
      ...DEFAULT_FILTERS,
      propertyTypes: ["villa"],
      roomsMin: 3,
      municipality: "Chieti",
    });

    expect(count).toBe(2);
  });
});

describe("owner request form", () => {
  const valid = {
    ...EMPTY_OWNER_FORM,
    fullName: "Mario Rossi",
    phone: "333 000 0000",
    intention: "decided" as const,
    privacyAccepted: true,
  };

  it("accepts a complete form", () => {
    expect(validateOwnerForm(valid)).toEqual({});
  });

  it("requires phone, intention and privacy consent", () => {
    const errors = validateOwnerForm({ ...EMPTY_OWNER_FORM, fullName: "Mario Rossi", phone: "12" });

    expect(Object.keys(errors).sort()).toEqual(["intention", "phone", "privacyAccepted"]);
  });

  it("sends the consent with the policy version and optional marketing", () => {
    const payload = toOwnerRequest({ ...valid, marketingAccepted: true, message: "  " });

    expect(payload).toMatchObject({
      kind: "sell",
      full_name: "Mario Rossi",
      intention: "decided",
      message: null,
      consent: {
        privacy_accepted: true,
        privacy_policy_version: "2026-01",
        marketing_accepted: true,
      },
    });
  });
});

describe("tCount", () => {
  it("uses the singular for one", () => {
    expect(tCount(1, "property.bathroom", "property.bathrooms")).toBe("1 bagno");
    expect(tCount(2, "property.bathroom", "property.bathrooms")).toBe("2 bagni");
  });
});

describe("layout", () => {
  it("keeps the phone layout on phones whatever their width", () => {
    expect(layoutFor(1280, "android")).toEqual({ isDesktop: false, areaWidth: 1280 });
  });

  it("shows narrow browser windows as a phone column", () => {
    expect(layoutFor(800, "web")).toEqual({ isDesktop: false, areaWidth: 480 });
    expect(layoutFor(390, "web")).toEqual({ isDesktop: false, areaWidth: 390 });
  });

  it("uses the sidebar layout in wide browser windows", () => {
    expect(layoutFor(1440, "web")).toEqual({ isDesktop: true, areaWidth: 1440 - SIDEBAR_WIDTH });
  });

  it("lays out one card per row on phones and up to three on desktop", () => {
    expect(gridFor(layoutFor(390, "web")).columns).toBe(1);
    expect(gridFor(layoutFor(1100, "web")).columns).toBe(2);
    expect(gridFor(layoutFor(1920, "web")).columns).toBe(3);
  });
});
