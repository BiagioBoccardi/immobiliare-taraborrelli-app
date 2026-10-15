import { it, type TranslationKey } from "./it";

export type { TranslationKey };

export function t(key: TranslationKey, params?: Record<string, string | number>): string {
  let text: string = it[key];
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

/** Translates a backend enum value, e.g. `tEnum("feature", "garden")`. Falls back to the value. */
export function tEnum(group: string, value: string | null | undefined): string {
  if (!value) return "—";
  const key = `enum.${group}.${value}`;
  return key in it ? it[key as TranslationKey] : value;
}

/** Count with the right Italian form: `1 bagno`, `2 bagni`. */
export function tCount(count: number, one: TranslationKey, many: TranslationKey): string {
  return count === 1 ? t(one) : t(many, { count });
}
