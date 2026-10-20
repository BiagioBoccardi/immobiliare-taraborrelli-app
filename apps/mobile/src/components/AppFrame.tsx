import type { ReactNode } from "react";
import { Platform, StyleSheet, useWindowDimensions, View } from "react-native";

import { colors } from "../theme";

/**
 * The app is designed for phones. In the browser preview it is shown in a centered
 * column as wide as a large phone, instead of being stretched across the desktop.
 */
export const APP_MAX_WIDTH = 480;

/** Width available to the app: the screen on phones, the centered column on desktop. */
export function useAppWidth(): number {
  const { width } = useWindowDimensions();
  return Platform.OS === "web" ? Math.min(width, APP_MAX_WIDTH) : width;
}

export function AppFrame({ children }: { children: ReactNode }) {
  if (Platform.OS !== "web") return <>{children}</>;
  return (
    <View style={styles.backdrop}>
      <View style={styles.column}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, alignItems: "center", backgroundColor: colors.gray100 },
  column: {
    flex: 1,
    width: "100%",
    maxWidth: APP_MAX_WIDTH,
    backgroundColor: colors.gray50,
    overflow: "hidden",
  },
});
