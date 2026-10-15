import { Ionicons } from "@expo/vector-icons";
import type { PropertyCard as Property } from "@taraborrelli/api-client";
import { Image } from "expo-image";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useFavorites } from "../favorites";
import { formatPrice, place } from "../format";
import { t, tCount, tEnum } from "../i18n";
import { cardShadow, colors, fonts, radii, spacing, typography } from "../theme";

export function FavoriteButton({
  id,
  size = 20,
  floating = true,
}: {
  id: string;
  size?: number;
  /** Floating over a photo (top right) or inline in a toolbar. */
  floating?: boolean;
}) {
  const { isFavorite, toggle } = useFavorites();
  const active = isFavorite(id);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={active ? t("property.removeFavorite") : t("property.addFavorite")}
      accessibilityState={{ selected: active }}
      hitSlop={8}
      onPress={() => toggle(id)}
      style={[styles.favoriteBase, floating && styles.favoriteFloating]}
    >
      <Ionicons
        name={active ? "heart" : "heart-outline"}
        size={size}
        color={active ? colors.danger : colors.gray700}
      />
    </Pressable>
  );
}

function Facts({ property }: { property: Property }) {
  const facts = [
    property.rooms ? tCount(property.rooms, "property.room", "property.rooms") : null,
    property.bathrooms
      ? tCount(property.bathrooms, "property.bathroom", "property.bathrooms")
      : null,
    t("common.sqm", { value: property.surface_sqm }),
  ].filter((fact): fact is string => fact !== null);
  return <Text style={styles.facts}>{facts.join(" · ")}</Text>;
}

/** Large card with the photo on top, used in lists. */
export function PropertyCard({ property }: { property: Property }) {
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${property.title}, ${formatPrice(property.price, property.contract)}`}
      onPress={() => router.push(`/immobile/${property.id}`)}
      style={styles.card}
    >
      <View>
        <Image
          source={property.cover_photo ? { uri: property.cover_photo.url } : undefined}
          style={styles.photo}
          contentFit="cover"
          transition={150}
        />
        <View style={styles.badges}>
          <Text style={styles.badge}>{tEnum("propertyType", property.property_type)}</Text>
          {property.status === "reserved" ? (
            <Text style={[styles.badge, styles.badgeWarning]}>{t("property.reserved")}</Text>
          ) : null}
        </View>
        <FavoriteButton id={property.id} />
      </View>
      <View style={styles.body}>
        <Text style={styles.price}>{formatPrice(property.price, property.contract)}</Text>
        <Text style={styles.title} numberOfLines={1}>
          {property.title}
        </Text>
        <View style={styles.placeRow}>
          <Ionicons name="location-outline" size={14} color={colors.gray500} />
          <Text style={styles.place} numberOfLines={1}>
            {place(property.municipality, property.zone)}
          </Text>
        </View>
        <Facts property={property} />
      </View>
    </Pressable>
  );
}

/** Narrow card for the horizontal "In evidenza" carousel. */
export function FeaturedCard({ property }: { property: Property }) {
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${property.title}, ${formatPrice(property.price, property.contract)}`}
      onPress={() => router.push(`/immobile/${property.id}`)}
      style={[styles.card, styles.featured]}
    >
      <View>
        <Image
          source={property.cover_photo ? { uri: property.cover_photo.url } : undefined}
          style={styles.featuredPhoto}
          contentFit="cover"
          transition={150}
        />
        <FavoriteButton id={property.id} />
      </View>
      <View style={styles.body}>
        <Text style={styles.price}>{formatPrice(property.price, property.contract)}</Text>
        <Text style={styles.title} numberOfLines={1}>
          {property.title}
        </Text>
        <Text style={styles.place} numberOfLines={1}>
          {place(property.municipality, property.zone)}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: radii.lg,
    overflow: "hidden",
    ...cardShadow,
  },
  photo: { width: "100%", aspectRatio: 4 / 3, backgroundColor: colors.gray100 },
  featured: { width: 260 },
  featuredPhoto: { width: "100%", height: 170, backgroundColor: colors.gray100 },
  badges: {
    position: "absolute",
    left: spacing.md,
    top: spacing.md,
    flexDirection: "row",
    gap: spacing.sm,
  },
  badge: {
    overflow: "hidden",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.brandLightBlueSoft,
    color: colors.brandBlue,
    fontSize: typography.sizes.xs,
    fontWeight: "600",
  },
  badgeWarning: { backgroundColor: colors.warningSoft, color: colors.warning },
  favoriteBase: {
    width: 40,
    height: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
    ...cardShadow,
  },
  favoriteFloating: { position: "absolute", right: spacing.md, top: spacing.md },
  body: { padding: spacing.lg, gap: spacing.xs },
  price: { fontSize: typography.sizes.lg, fontWeight: "700", color: colors.brandBlue },
  title: { fontFamily: fonts.heading, fontSize: typography.sizes.lg, color: colors.gray900 },
  placeRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  place: { fontSize: typography.sizes.sm, color: colors.gray500, flexShrink: 1 },
  facts: { fontSize: typography.sizes.sm, color: colors.gray700, marginTop: spacing.xs },
});
