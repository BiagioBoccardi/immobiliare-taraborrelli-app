import type { ReactNode } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useLayout } from "../layout";
import { colors, spacing } from "../theme";

/** Login and registration on desktop: the whole window in brand blue, the form centered. */
export function useAuthOnDark(): boolean {
  return useLayout().isDesktop;
}

export function AuthLayout({ children }: { children: ReactNode }) {
  const onDark = useAuthOnDark();
  return (
    <SafeAreaView style={[styles.safe, onDark && styles.safeDark]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={[styles.content, onDark && styles.contentDark]}
          keyboardShouldPersistTaps="handled"
        >
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.white },
  safeDark: { backgroundColor: colors.brandBlue },
  flex: { flex: 1 },
  content: { padding: spacing.xl, gap: spacing.lg },
  contentDark: {
    flexGrow: 1,
    justifyContent: "center",
    width: "100%",
    maxWidth: 520,
    gap: spacing.xl,
    alignSelf: "center",
    paddingVertical: spacing.xxxl,
  },
});
