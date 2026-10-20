import type { ReactNode } from "react";
import { ScrollView, StyleSheet, type StyleProp, type ViewStyle } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CONTENT_MAX_WIDTH, DESKTOP_PADDING, NARROW_MAX_WIDTH, useLayout } from "../layout";
import { colors, spacing } from "../theme";

/** Space kept free at the bottom of tab screens for the floating tab bar. */
export const TAB_BAR_SPACE = 112;

/**
 * Padding of a tab screen's content. On desktop the content is centered and limited in
 * width: `wide` for lists and grids, `narrow` for forms and text.
 */
export function useScreenContentStyle(width: "wide" | "narrow" = "wide"): StyleProp<ViewStyle> {
  const { isDesktop } = useLayout();
  if (!isDesktop) return styles.content;
  return [styles.desktop, { maxWidth: width === "wide" ? CONTENT_MAX_WIDTH : NARROW_MAX_WIDTH }];
}

export function Screen({
  children,
  scroll = true,
  width = "wide",
  contentStyle,
}: {
  children: ReactNode;
  scroll?: boolean;
  width?: "wide" | "narrow";
  contentStyle?: StyleProp<ViewStyle>;
}) {
  const layoutStyle = useScreenContentStyle(width);
  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      {scroll ? (
        <ScrollView
          contentContainerStyle={[layoutStyle, contentStyle]}
          keyboardShouldPersistTaps="handled"
        >
          {children}
        </ScrollView>
      ) : (
        children
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.xl, paddingBottom: TAB_BAR_SPACE, gap: spacing.xl },
  desktop: {
    width: "100%",
    alignSelf: "center",
    padding: DESKTOP_PADDING,
    gap: spacing.xl,
  },
});
