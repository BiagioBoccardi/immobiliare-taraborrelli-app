/**
 * Prices in the Italian format required by the brand: `120.000 €`.
 * Thousands are always grouped (Intl's it-IT leaves 4-digit numbers ungrouped, e.g. "1500").
 */
export function formatEuro(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const sign = value < 0 ? "-" : "";
  const digits = String(Math.round(Math.abs(value)));
  return `${sign}${digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".")} €`;
}

const dateFormat = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const dateTimeFormat = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateFormat.format(new Date(iso)) : "—";
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFormat.format(new Date(iso)) : "—";
}

/** ISO date-time → value for `<input type="datetime-local">` in the browser's time zone. */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

/** Value of `<input type="datetime-local">` → ISO string with time zone, or null if empty. */
export function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

/** Phone number in international form for tel: and WhatsApp links (Italian numbers by default). */
export function internationalPhone(phone: string): string {
  const digits = phone.replace(/[^\d+]/g, "");
  return digits.startsWith("+") ? digits : `+39${digits}`;
}
