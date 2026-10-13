/**
 * Shared design tokens. Every color, spacing and font used by the apps comes from here.
 *
 * The brand colors are placeholders until the agency provides the exact codes and the logo
 * (open decision in CLAUDE.md, section 14): blue and light blue of the brand, white, light gray.
 */

export const colors = {
  brandBlue: "#1F4E8C",
  brandBlueDark: "#163A69",
  brandLightBlue: "#5BA4D9",
  brandLightBlueSoft: "#E6F1FA",
  white: "#FFFFFF",
  gray50: "#F5F7FA",
  gray100: "#EBEEF3",
  gray300: "#C9D0DA",
  gray500: "#7A8494",
  gray700: "#3E4756",
  gray900: "#1B212B",
  success: "#2E7D5B",
  successSoft: "#E3F3EC",
  warning: "#A86A00",
  warningSoft: "#FBF0DC",
  danger: "#B42318",
  dangerSoft: "#FDE8E6",
  overlay: "rgba(27, 33, 43, 0.45)",
} as const;

export const spacing = {
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const radii = {
  sm: 6,
  md: 10,
  lg: 16,
  pill: 999,
} as const;

export const typography = {
  fontFamily:
    "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  sizes: {
    xs: 12,
    sm: 14,
    md: 16,
    lg: 18,
    xl: 22,
    xxl: 28,
    display: 36,
  },
  weights: {
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  lineHeight: 1.5,
} as const;

export const shadows = {
  card: "0 1px 2px rgba(27, 33, 43, 0.06), 0 2px 8px rgba(27, 33, 43, 0.06)",
  overlay: "0 12px 32px rgba(27, 33, 43, 0.18)",
} as const;

export const theme = { colors, spacing, radii, typography, shadows } as const;
export type Theme = typeof theme;

/** CSS custom properties for web apps, e.g. `--color-brand-blue`, `--space-md`. */
export function cssVariables(): Record<string, string> {
  const kebab = (name: string): string => name.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
  const vars: Record<string, string> = {};
  for (const [name, value] of Object.entries(colors)) vars[`--color-${kebab(name)}`] = value;
  for (const [name, value] of Object.entries(spacing)) vars[`--space-${name}`] = `${value}px`;
  for (const [name, value] of Object.entries(radii)) vars[`--radius-${name}`] = `${value}px`;
  for (const [name, value] of Object.entries(typography.sizes))
    vars[`--font-size-${name}`] = `${value}px`;
  for (const [name, value] of Object.entries(typography.weights))
    vars[`--font-weight-${name}`] = `${value}`;
  for (const [name, value] of Object.entries(shadows)) vars[`--shadow-${name}`] = value;
  vars["--font-family"] = typography.fontFamily;
  vars["--line-height"] = `${typography.lineHeight}`;
  return vars;
}
