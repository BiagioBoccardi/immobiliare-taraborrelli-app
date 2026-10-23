import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, usePathname, type Href } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { images } from "../assets";
import { agency } from "../config";
import { t, type TranslationKey } from "../i18n";
import { SIDEBAR_WIDTH } from "../layout";
import { useSession } from "../session";
import { colors, radii, spacing, typography } from "../theme";
import type { IconName } from "./ui";

const ITEMS: {
  href: Href;
  path: string;
  label: TranslationKey;
  icon: IconName;
  activeIcon: IconName;
}[] = [
  { href: "/", path: "/", label: "tabs.home", icon: "home-outline", activeIcon: "home" },
  {
    href: "/cerca",
    path: "/cerca",
    label: "tabs.search",
    icon: "search-outline",
    activeIcon: "search",
  },
  {
    href: "/preferiti",
    path: "/preferiti",
    label: "tabs.favorites",
    icon: "heart-outline",
    activeIcon: "heart",
  },
  { href: "/vendi", path: "/vendi", label: "tabs.sell", icon: "key-outline", activeIcon: "key" },
  {
    href: "/profilo",
    path: "/profilo",
    label: "tabs.profile",
    icon: "person-outline",
    activeIcon: "person",
  },
];

/** Tools reachable from the sidebar besides the five sections of the tab bar. */
const TOOLS: (typeof ITEMS)[number][] = [
  {
    href: "/mutuo",
    path: "/mutuo",
    label: "tabs.mortgage",
    icon: "calculator-outline",
    activeIcon: "calculator",
  },
];

function SidebarItem({ item, active }: { item: (typeof ITEMS)[number]; active: boolean }) {
  const [hovered, setHovered] = useState(false);
  const label = t(item.label);
  return (
    <Pressable
      accessibilityRole="tab"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
      onPress={() => router.navigate(item.href)}
      onHoverIn={() => setHovered(true)}
      onHoverOut={() => setHovered(false)}
      style={[styles.item, hovered && !active && styles.itemHover, active && styles.itemActive]}
    >
      <Ionicons
        name={active ? item.activeIcon : item.icon}
        size={22}
        color={active ? colors.brandBlue : colors.white}
      />
      <Text style={[styles.label, active && styles.labelActive]}>{label}</Text>
    </Pressable>
  );
}

/** Desktop navigation: the same five sections as the phone tab bar, always visible. */
export function Sidebar() {
  const pathname = usePathname();
  const { user } = useSession();

  return (
    <View style={styles.sidebar}>
      <Pressable
        accessibilityRole="link"
        onPress={() => router.navigate("/")}
        style={styles.logoLink}
      >
        <Image
          source={images.logoWhite}
          style={styles.logo}
          contentFit="contain"
          accessibilityLabel={agency.name}
        />
      </Pressable>

      <View style={styles.nav} accessibilityRole="tablist">
        {ITEMS.map((item) => (
          <SidebarItem key={item.path} item={item} active={pathname === item.path} />
        ))}
        <View style={styles.separator} />
        {TOOLS.map((item) => (
          <SidebarItem key={item.path} item={item} active={pathname === item.path} />
        ))}
      </View>

      <View style={styles.contact}>
        <Text style={styles.contactTitle}>{t("home.actionContact")}</Text>
        <Text style={styles.contactText}>{agency.area}</Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => router.push("/contatti")}
          style={styles.contactButton}
        >
          <Ionicons name="call" size={18} color={colors.brandBlue} />
          <Text style={styles.contactButtonText}>{t("profile.contact")}</Text>
        </Pressable>
      </View>

      {user ? (
        <Pressable
          accessibilityRole="link"
          onPress={() => router.navigate("/profilo")}
          style={styles.user}
        >
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{user.full_name.trim().charAt(0).toUpperCase()}</Text>
          </View>
          <View style={styles.userText}>
            <Text style={styles.userName} numberOfLines={1}>
              {user.full_name}
            </Text>
            <Text style={styles.userEmail} numberOfLines={1}>
              {user.email}
            </Text>
          </View>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  sidebar: {
    width: SIDEBAR_WIDTH,
    padding: spacing.lg,
    gap: spacing.xl,
    backgroundColor: colors.brandBlueDark,
  },
  logoLink: { paddingVertical: spacing.md, alignItems: "center" },
  logo: { width: 176, aspectRatio: 868 / 480 },
  nav: { gap: spacing.xs, flex: 1 },
  separator: {
    height: 1,
    marginVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    backgroundColor: colors.brandBlue,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    height: 48,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.pill,
  },
  itemHover: { backgroundColor: colors.brandBlue },
  itemActive: { backgroundColor: colors.white },
  label: { color: colors.white, fontSize: typography.sizes.md, fontWeight: "500" },
  labelActive: { color: colors.brandBlue, fontWeight: "600" },
  contact: {
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radii.lg,
    backgroundColor: colors.brandBlue,
  },
  contactTitle: { color: colors.white, fontSize: typography.sizes.md, fontWeight: "600" },
  contactText: { color: colors.brandLightBlueSoft, fontSize: typography.sizes.sm },
  contactButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    height: 40,
    marginTop: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.white,
  },
  contactButtonText: { color: colors.brandBlue, fontWeight: "600", fontSize: typography.sizes.sm },
  user: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandLightBlue,
  },
  avatarText: { color: colors.white, fontWeight: "700", fontSize: typography.sizes.md },
  userText: { flex: 1 },
  userName: { color: colors.white, fontWeight: "600", fontSize: typography.sizes.sm },
  userEmail: { color: colors.brandLightBlueSoft, fontSize: typography.sizes.xs },
});
