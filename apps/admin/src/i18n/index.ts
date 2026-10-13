import { it, type TranslationKey } from "./it";

export type { TranslationKey };

type Params = Record<string, string | number>;

/** Translates a key, replacing `{name}` placeholders with the given parameters. */
export function t(key: TranslationKey, params?: Params): string {
  let text: string = it[key];
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

export function hasTranslation(key: string): key is TranslationKey {
  return key in it;
}

/** Translates a backend enum value, e.g. `tEnum("leadStatus", "new")`. Falls back to the value. */
export function tEnum(group: string, value: string | null | undefined): string {
  if (!value) return it["common.none"];
  const key = `enum.${group}.${value}`;
  return key in it ? it[key as TranslationKey] : value;
}

/** Message for an API error code, with a generic fallback. */
export function tError(code: string | undefined): string {
  const key = `errors.${code ?? "generic"}`;
  return key in it ? it[key as TranslationKey] : it["errors.generic"];
}
