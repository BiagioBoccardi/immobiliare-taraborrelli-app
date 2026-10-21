import { usePathname } from "expo-router";
import type { ReactNode } from "react";
import { Platform, StyleSheet, View } from "react-native";

import { PHONE_MAX_WIDTH, useLayout } from "../layout";
import { useSession } from "../session";
import { colors } from "../theme";
import { Sidebar } from "./Sidebar";

/** Screens shown on their own, without navigation: welcome, login and registration. */
const STANDALONE = ["/benvenuto", "/accedi", "/registrati"];

/**
 * Browser layout. Wide windows get the full width, with the sidebar once logged in; narrow
 * windows get the phone layout in a centered column. Phones are unchanged.
 *
 * The tree keeps the same shape in every case, so resizing the window or logging in never
 * remounts the navigator (which would lose the current screen).
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { isDesktop } = useLayout();
  const pathname = usePathname();
  const { status } = useSession();
  if (Platform.OS !== "web") return <>{children}</>;

  const standalone = status !== "authenticated" || STANDALONE.includes(pathname);
  const withSidebar = isDesktop && !standalone;
  return (
    <View style={styles.backdrop}>
      {withSidebar ? <Sidebar /> : null}
      {/* On desktop the welcome and login screens fill the window (in brand blue). */}
      <View style={isDesktop ? styles.area : styles.phone}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    flexDirection: "row",
    justifyContent: "center",
    backgroundColor: colors.gray100,
  },
  area: { flex: 1, backgroundColor: colors.gray50, overflow: "hidden" },
  phone: {
    flex: 1,
    maxWidth: PHONE_MAX_WIDTH,
    backgroundColor: colors.gray50,
    overflow: "hidden",
  },
});
