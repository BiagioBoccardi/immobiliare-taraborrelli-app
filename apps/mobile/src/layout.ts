import { Platform, useWindowDimensions, type ViewStyle } from "react-native";

import { colors, spacing } from "./theme";

/** From this window width the browser shows the desktop layout with the sidebar. */
export const DESKTOP_MIN_WIDTH = 1024;
/** Width of the phone column used in narrow browser windows. */
export const PHONE_MAX_WIDTH = 480;
export const SIDEBAR_WIDTH = 264;
/** Content width limits on desktop: lists and grids, forms and text. */
export const CONTENT_MAX_WIDTH = 1200;
export const NARROW_MAX_WIDTH = 720;
export const DESKTOP_PADDING = spacing.xxl;

export interface Layout {
  isDesktop: boolean;
  /** Width of the area next to the sidebar (desktop) or of the phone screen. */
  areaWidth: number;
}

export function layoutFor(windowWidth: number, os: string = Platform.OS): Layout {
  if (os !== "web") return { isDesktop: false, areaWidth: windowWidth };
  if (windowWidth >= DESKTOP_MIN_WIDTH) {
    return { isDesktop: true, areaWidth: windowWidth - SIDEBAR_WIDTH };
  }
  return { isDesktop: false, areaWidth: Math.min(windowWidth, PHONE_MAX_WIDTH) };
}

export function useLayout(): Layout {
  const { width } = useWindowDimensions();
  return layoutFor(width);
}

export interface Grid {
  columns: number;
  itemWidth: number | undefined;
}

/** Columns for property cards: one on phones, as many as fit on desktop (max 3). */
export function gridFor(layout: Layout, minItemWidth = 300, gap: number = spacing.lg): Grid {
  if (!layout.isDesktop) return { columns: 1, itemWidth: undefined };
  const inner = Math.min(layout.areaWidth, CONTENT_MAX_WIDTH) - 2 * DESKTOP_PADDING;
  const columns = Math.max(1, Math.min(3, Math.floor((inner + gap) / (minItemWidth + gap))));
  return { columns, itemWidth: (inner - gap * (columns - 1)) / columns };
}

export function useGrid(minItemWidth?: number): Grid {
  return gridFor(useLayout(), minItemWidth);
}

/** Modal screens (filters, contacts) on desktop: a centered panel instead of the full area. */
export const desktopPanel: ViewStyle = {
  width: "100%",
  maxWidth: 560,
  alignSelf: "center",
  borderLeftWidth: 1,
  borderRightWidth: 1,
  borderColor: colors.gray100,
};

/** Buy/rent switch on desktop: as wide as a phone control, not the whole page. */
export const desktopControl: ViewStyle = { width: "100%", maxWidth: 400 };
