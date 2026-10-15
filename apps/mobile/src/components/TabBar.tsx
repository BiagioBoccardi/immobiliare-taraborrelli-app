import { Ionicons } from "@expo/vector-icons";
import type { Tabs } from "expo-router";
import type { ComponentProps } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { t, type TranslationKey } from "../i18n";
import { colors, radii, spacing, typography } from "../theme";
import type { IconName } from "./ui";

type TabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>["tabBar"]>>[0];

const TABS: Record<string, { label: TranslationKey; icon: IconName; activeIcon: IconName }> = {
  index: { label: "tabs.home", icon: "home-outline", activeIcon: "home" },
  cerca: { label: "tabs.search", icon: "search-outline", activeIcon: "search" },
  preferiti: { label: "tabs.favorites", icon: "heart-outline", activeIcon: "heart" },
  vendi: { label: "tabs.sell", icon: "key-outline", activeIcon: "key" },
  profilo: { label: "tabs.profile", icon: "person-outline", activeIcon: "person" },
};

/** Rounded dark bar with five sections; the active one shows its label (reference images). */
export function TabBar({ state, navigation }: TabBarProps) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.wrapper, { paddingBottom: Math.max(insets.bottom, spacing.md) }]}>
      <View style={styles.bar} accessibilityRole="tablist">
        {state.routes.map((route, index) => {
          const tab = TABS[route.name];
          if (!tab) return null;
          const focused = state.index === index;
          const label = t(tab.label);
          return (
            <Pressable
              key={route.key}
              accessibilityRole="tab"
              accessibilityLabel={label}
              accessibilityState={{ selected: focused }}
              onPress={() => {
                const event = navigation.emit({
                  type: "tabPress",
                  target: route.key,
                  canPreventDefault: true,
                });
                if (!focused && !event.defaultPrevented) navigation.navigate(route.name);
              }}
              style={[styles.item, focused && styles.itemActive]}
            >
              <Ionicons
                name={focused ? tab.activeIcon : tab.icon}
                size={22}
                color={focused ? colors.brandBlue : colors.white}
              />
              {focused ? (
                <Text style={styles.label} numberOfLines={1}>
                  {label}
                </Text>
              ) : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.lg,
  },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing.sm,
    borderRadius: radii.pill,
    backgroundColor: colors.brandBlueDark,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    height: 48,
    minWidth: 48,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
  },
  itemActive: { backgroundColor: colors.white, paddingHorizontal: spacing.lg },
  label: { color: colors.brandBlue, fontWeight: "600", fontSize: typography.sizes.sm },
});
