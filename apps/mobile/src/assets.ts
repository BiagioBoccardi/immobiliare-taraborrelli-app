/* eslint-disable @typescript-eslint/no-require-imports -- Metro bundles static files referenced with require() */
import type { FontSource } from "expo-font";
import type { ImageSourcePropType } from "react-native";

/** Brand files from the shared theme package. */
export const images: Record<"logo" | "logoWhite" | "icon", ImageSourcePropType> = {
  logo: require("@taraborrelli/theme/assets/logo.png"),
  logoWhite: require("@taraborrelli/theme/assets/logo-white.png"),
  icon: require("@taraborrelli/theme/assets/icon-192.png"),
};

export const headingFontFile: FontSource = require("@taraborrelli/theme/assets/fonts/EBGaramond_600SemiBold.ttf");
