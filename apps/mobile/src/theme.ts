import { colors, radii, shadows, spacing, typography } from "@taraborrelli/theme";

export { colors, radii, shadows, spacing, typography };

/** Font family names registered with expo-font in app/_layout.tsx. */
export const fonts = {
  heading: "EBGaramond-SemiBold",
} as const;

/** Shadow for cards on native (the shared token is a CSS value for the web). */
export const cardShadow = {
  shadowColor: colors.gray900,
  shadowOpacity: 0.08,
  shadowRadius: 12,
  shadowOffset: { width: 0, height: 4 },
  elevation: 3,
} as const;
