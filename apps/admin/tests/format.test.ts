import { t, tEnum, tError } from "../src/i18n";
import { formatEuro, fromLocalInput, internationalPhone, toLocalInput } from "../src/utils/format";

describe("formatEuro", () => {
  it.each([
    [120000, "120.000 €"],
    [1500, "1.500 €"],
    [280, "280 €"],
    [1250000, "1.250.000 €"],
  ])("formats %d as %s", (value, expected) => {
    expect(formatEuro(value)).toBe(expected);
  });

  it("shows a dash when the value is missing", () => {
    expect(formatEuro(null)).toBe("—");
  });
});

describe("internationalPhone", () => {
  it("adds the Italian prefix to national numbers", () => {
    expect(internationalPhone("333 000 0000")).toBe("+393330000000");
  });

  it("keeps numbers that already have a prefix", () => {
    expect(internationalPhone("+41 79 000 00 00")).toBe("+41790000000");
  });
});

describe("datetime-local conversion", () => {
  it("round-trips a date through the input value", () => {
    const iso = "2026-10-20T08:30:00.000Z";

    expect(fromLocalInput(toLocalInput(iso))).toBe(iso);
  });

  it("converts an empty input to null", () => {
    expect(fromLocalInput("")).toBeNull();
  });
});

describe("i18n", () => {
  it("replaces placeholders", () => {
    expect(t("common.page", { page: 2, pages: 5 })).toBe("Pagina 2 di 5");
  });

  it("translates enum values and falls back to the raw value", () => {
    expect(tEnum("leadStatus", "mandate_acquired")).toBe("Incarico acquisito");
    expect(tEnum("leadStatus", "unknown_value")).toBe("unknown_value");
  });

  it("uses a generic message for unknown error codes", () => {
    expect(tError("something_new")).toBe(t("errors.generic"));
  });
});
