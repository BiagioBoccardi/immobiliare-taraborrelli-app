import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router } from "expo-router";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { images } from "../../src/assets";
import { FeaturedCard, PropertyCard } from "../../src/components/PropertyCard";
import { Screen } from "../../src/components/Screen";
import {
  Body,
  EmptyState,
  ErrorState,
  Heading,
  Loading,
  SectionHeader,
  Segmented,
  type IconName,
} from "../../src/components/ui";
import { t, type TranslationKey } from "../../src/i18n";
import { useFeatured, useLatest } from "../../src/queries";
import { useSearch } from "../../src/search";
import { useSession } from "../../src/session";
import { cardShadow, colors, radii, spacing, typography } from "../../src/theme";

const ACTIONS: { label: TranslationKey; icon: IconName; go: () => void }[] = [
  { label: "home.actionSearch", icon: "search", go: () => router.navigate("/cerca") },
  { label: "home.actionSell", icon: "key", go: () => router.navigate("/vendi") },
  { label: "home.actionContact", icon: "call", go: () => router.push("/contatti") },
];

export default function Home() {
  const { filters, update } = useSearch();
  const { user } = useSession();
  const firstName = user?.full_name.trim().split(/\s+/)[0];
  const featured = useFeatured(filters.contract);
  const latest = useLatest(filters.contract);

  return (
    <Screen>
      <View style={styles.header}>
        <View style={styles.greeting}>
          <Heading size="xxl">
            {firstName ? t("home.greetingName", { name: firstName }) : t("home.greeting")}
          </Heading>
          <View style={styles.location}>
            <Ionicons name="location-outline" size={16} color={colors.brandBlue} />
            <Body muted>{t("home.location")}</Body>
          </View>
        </View>
        <Image source={images.icon} style={styles.icon} accessibilityIgnoresInvertColors />
      </View>

      <Segmented
        options={[
          { value: "sale", label: t("home.buy") },
          { value: "rent", label: t("home.rent") },
        ]}
        value={filters.contract}
        onChange={(contract) => update({ contract })}
      />

      <Pressable
        accessibilityRole="search"
        onPress={() => router.navigate("/cerca")}
        style={styles.searchBar}
      >
        <Ionicons name="search-outline" size={20} color={colors.gray500} />
        <Text style={styles.searchText}>{t("home.searchPlaceholder")}</Text>
      </Pressable>

      <View style={styles.actions}>
        {ACTIONS.map((action) => (
          <Pressable
            key={action.label}
            accessibilityRole="button"
            onPress={action.go}
            style={styles.action}
          >
            <View style={styles.actionIcon}>
              <Ionicons name={action.icon} size={22} color={colors.white} />
            </View>
            <Text style={styles.actionLabel}>{t(action.label)}</Text>
          </Pressable>
        ))}
      </View>

      <View>
        <SectionHeader
          title={t("home.featured")}
          actionLabel={t("common.seeAll")}
          onAction={() => router.navigate("/cerca")}
        />
        {featured.isPending ? <Loading /> : null}
        {featured.isError ? <ErrorState onRetry={() => void featured.refetch()} /> : null}
        {featured.data && featured.data.items.length > 0 ? (
          <FlatList
            horizontal
            data={featured.data.items}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => <FeaturedCard property={item} />}
            ItemSeparatorComponent={() => <View style={{ width: spacing.lg }} />}
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.carousel}
            style={styles.carouselList}
          />
        ) : null}
      </View>

      <View style={styles.latest}>
        <SectionHeader title={t("home.latest")} />
        {latest.isPending ? <Loading /> : null}
        {latest.isError ? <ErrorState onRetry={() => void latest.refetch()} /> : null}
        {latest.data && latest.data.items.length === 0 ? (
          <EmptyState icon="home-outline" title={t("home.empty")} />
        ) : null}
        {latest.data?.items.map((property) => (
          <PropertyCard key={property.id} property={property} />
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  greeting: { gap: spacing.xs },
  location: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  icon: { width: 48, height: 48 },
  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    height: 52,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.pill,
    backgroundColor: colors.white,
    ...cardShadow,
  },
  searchText: { color: colors.gray500, fontSize: typography.sizes.md },
  actions: { flexDirection: "row", gap: spacing.md },
  action: {
    flex: 1,
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.lg,
    borderRadius: radii.lg,
    backgroundColor: colors.white,
    ...cardShadow,
  },
  actionIcon: {
    width: 44,
    height: 44,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandBlue,
  },
  actionLabel: { fontSize: typography.sizes.sm, fontWeight: "600", color: colors.gray900 },
  carouselList: { marginHorizontal: -spacing.xl },
  carousel: { paddingHorizontal: spacing.xl, paddingVertical: spacing.xs },
  latest: { gap: spacing.lg },
});
