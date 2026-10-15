import { cssVariables, headingFont } from "@taraborrelli/theme";
import headingFontUrl from "@taraborrelli/theme/assets/fonts/eb-garamond-latin-wght-normal.woff2";

/** Exposes the shared design tokens as CSS custom properties on the document root. */
export function applyTheme(root: HTMLElement = document.documentElement): void {
  for (const [name, value] of Object.entries(cssVariables())) {
    root.style.setProperty(name, value);
  }
  loadHeadingFont();
}

/** Registers the serif used by the titles. Until it loads, the fallback serif is shown. */
function loadHeadingFont(): void {
  if (typeof FontFace === "undefined" || !("fonts" in document)) return;
  const face = new FontFace(headingFont.family, `url(${headingFontUrl}) format("woff2")`, {
    weight: headingFont.weights,
    style: "normal",
    display: "swap",
  });
  document.fonts.add(face);
  void face.load().catch(() => undefined);
}
