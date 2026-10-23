import { formatEuro, formatPrice, place, whatsappUrl } from "../src/format";
import { tCount } from "../src/i18n";
import { viewerHtml } from "../src/components/ModelViewer";
import { photosToLoad } from "../src/gallery";
import { gridFor, layoutFor, SIDEBAR_WIDTH } from "../src/layout";
import {
  computeMortgage,
  defaultDownPayment,
  monthlyPayment,
  parseNumber,
  validateMortgage,
} from "../src/mortgage";
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

describe("mortgage", () => {
  it("computes the payment with French amortization", () => {
    const result = computeMortgage({ price: 150000, downPayment: 30000, years: 25, annualRate: 3 });

    expect(result.loan).toBe(120000);
    expect(result.monthlyPayment).toBeCloseTo(569.05, 2);
    expect(result.totalInterest).toBeCloseTo(result.monthlyPayment * 300 - 120000, 6);
    expect(result.loanShare).toBeCloseTo(0.8);
  });

  it("splits the loan evenly with a zero rate", () => {
    expect(monthlyPayment(120000, 0, 10)).toBe(1000);
  });

  it.each([
    ["120.000", 120000],
    ["120000 €", 120000],
    ["3,5", 3.5],
    ["3.5", 3.5],
    ["1.250.000", 1250000],
    ["", null],
    ["abc", null],
  ])("reads %p as %p", (text, expected) => {
    expect(parseNumber(text)).toBe(expected);
  });

  it("rejects a down payment equal to the price and an impossible rate", () => {
    expect(validateMortgage({ price: 100000, downPayment: 100000, years: 20, annualRate: 3 })).toBe(
      "invalidDownPayment",
    );
    expect(validateMortgage({ price: 100000, downPayment: 0, years: 20, annualRate: 30 })).toBe(
      "invalidRate",
    );
    expect(validateMortgage({ price: 0, downPayment: 0, years: 20, annualRate: 3 })).toBe(
      "invalidPrice",
    );
  });

  it("suggests a 20% down payment rounded to the thousand", () => {
    expect(defaultDownPayment(139000)).toBe(28000);
  });
});

describe("3D viewer page", () => {
  it("escapes the model address and the title", () => {
    const html = viewerHtml('https://media.test/a.glb?x="1"', "Casa <bella>");

    expect(html).toContain('src="https://media.test/a.glb?x=&quot;1&quot;"');
    expect(html).toContain('alt="Casa &lt;bella>"');
    expect(html).toContain("@google/model-viewer@4.4.0");
  });
});

describe("photo gallery loading", () => {
  it("downloads the current photo and its neighbors first", () => {
    expect([...photosToLoad(new Set(), 0, 11)].sort((a, b) => a - b)).toEqual([0, 1]);
  });

  it("keeps the photos already seen", () => {
    const loaded = photosToLoad(new Set([0, 1]), 5, 11);

    expect([...loaded].sort((a, b) => a - b)).toEqual([0, 1, 4, 5, 6]);
  });

  it("stays within the photos of the property", () => {
    expect([...photosToLoad(new Set(), 10, 11)].sort((a, b) => a - b)).toEqual([9, 10]);
  });
});
