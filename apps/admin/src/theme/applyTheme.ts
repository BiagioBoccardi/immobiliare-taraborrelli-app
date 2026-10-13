import { cssVariables } from "@taraborrelli/theme";

/** Exposes the shared design tokens as CSS custom properties on the document root. */
export function applyTheme(root: HTMLElement = document.documentElement): void {
  for (const [name, value] of Object.entries(cssVariables())) {
    root.style.setProperty(name, value);
  }
}
