import { t } from "./i18n";

/** Prices in the Italian format: `120.000 €`. */
export function formatEuro(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const digits = String(Math.round(Math.abs(value)));
  return `${value < 0 ? "-" : ""}${digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".")} €`;
}

export function formatPrice(price: number, contract: "sale" | "rent"): string {
  return contract === "rent" ? `${formatEuro(price)}${t("property.perMonth")}` : formatEuro(price);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [year, month, day] = iso.slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}

export function place(municipality: string, zone: string | null | undefined): string {
  return zone ? `${zone}, ${municipality}` : municipality;
}

/** Digits only, for WhatsApp links (wa.me needs the international number without "+"). */
export function whatsappUrl(number: string, message: string): string {
  return `https://wa.me/${number.replace(/\D/g, "")}?text=${encodeURIComponent(message)}`;
}
