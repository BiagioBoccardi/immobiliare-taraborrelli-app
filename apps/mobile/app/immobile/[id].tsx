import { Ionicons } from "@expo/vector-icons";
import type { PropertyDetail } from "@taraborrelli/api-client";
import { Image } from "expo-image";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { FlatList, Pressable, ScrollView, Share, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAppWidth } from "../../src/components/AppFrame";
import { FavoriteButton } from "../../src/components/PropertyCard";
import {
  Body,
  Button,
  EmptyState,
  ErrorState,
  Heading,
  Loading,
  type IconName,
} from "../../src/components/ui";
import { agency } from "../../src/config";
import { contact } from "../../src/contact";
import { formatDate, formatEuro, formatPrice, place } from "../../src/format";
import { t, tCount, tEnum } from "../../src/i18n";
import { isNotFound, useProperty } from "../../src/queries";
import { cardShadow, colors, radii, spacing, typography } from "../../src/theme";

function Gallery({ property }: { property: PropertyDetail }) {
  const width = useAppWidth();
  const [index, setIndex] = useState(0);
  const photos = property.photos;
  return (
    <View>
      <FlatList
        horizontal
        pagingEnabled
        data={photos}
        keyExtractor={(photo) => photo.id}
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={(event) =>
          setIndex(Math.round(event.nativeEvent.contentOffset.x / width))
        }
        renderItem={({ item, index: i }) => (
          <Image
            source={{ uri: item.url }}
            style={{ width, height: width * 0.85 }}
            contentFit="cover"
            transition={150}
            accessibilityLabel={
              item.caption ?? t("property.photo", { index: i + 1, total: photos.length })
            }
          />
        )}
        ListEmptyComponent={
          <View style={{ width, height: width * 0.6, backgroundColor: colors.gray100 }} />
        }
      />
      {photos.length > 1 ? (
        <Text style={styles.counter}>
          {index + 1}/{photos.length}
        </Text>
      ) : null}
    </View>
  );
}

function Fact({ icon, label }: { icon: IconName; label: string }) {
  return (
    <View style={styles.fact}>
      <Ionicons name={icon} size={18} color={colors.brandBlue} />
      <Text style={styles.factText}>{label}</Text>
    </View>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Body muted>{label}</Body>
      <Body style={styles.detailValue}>{value}</Body>
    </View>
  );
}

export default function PropertyScreen() {
  const { id = "" } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const property = useProperty(id);

  if (property.isPending) return <Loading />;
  if (property.isError || !property.data) {
    return (
      <View style={[styles.missing, { paddingTop: insets.top + spacing.xl }]}>
        {isNotFound(property.error) ? (
          <EmptyState
            icon="home-outline"
            title={t("property.notFound")}
            action={
              <Button label={t("common.back")} variant="secondary" onPress={() => router.back()} />
            }
          />
        ) : (
          <ErrorState onRetry={() => void property.refetch()} />
        )}
      </View>
    );
  }

  const data = property.data;
  const price = formatPrice(data.price, data.contract);
  const where = place(data.municipality, data.zone);
  const reference = t("property.reference", { reference: data.reference });

  const share = () =>
    Share.share({
      message: t("property.share", {
        title: data.title,
        price,
        place: where,
        reference: data.reference,
        agency: agency.name,
      }),
    });

  const details: [string, string][] = [
    data.floor !== null && data.floor !== undefined
      ? [t("property.floor"), String(data.floor)]
      : null,
    data.condition ? [t("property.condition"), tEnum("condition", data.condition)] : null,
    data.energy_class ? [t("property.energyClass"), data.energy_class] : null,
    data.year_built ? [t("property.yearBuilt"), String(data.year_built)] : null,
    data.condominium_fees
      ? [
          t("property.condominiumFees"),
          `${formatEuro(data.condominium_fees)}${t("property.perMonth")}`,
        ]
      : null,
    data.accommodation
      ? [t("property.accommodation"), tEnum("accommodation", data.accommodation)]
      : null,
    data.tenant_types.length
      ? [t("property.tenants"), data.tenant_types.map((x) => tEnum("tenantType", x)).join(", ")]
      : null,
    data.available_from ? [t("property.availableFrom"), formatDate(data.available_from)] : null,
  ].filter((row): row is [string, string] => row !== null);

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={{ paddingBottom: 120 + insets.bottom }}>
        <Gallery property={data} />
        <View style={[styles.topButtons, { top: insets.top + spacing.sm }]}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("common.back")}
            onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))}
            style={styles.roundButton}
          >
            <Ionicons name="chevron-back" size={22} color={colors.gray900} />
          </Pressable>
          <View style={styles.row}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("property.shareLabel")}
              onPress={() => void share()}
              style={styles.roundButton}
            >
              <Ionicons name="share-outline" size={20} color={colors.gray900} />
            </Pressable>
            <FavoriteButton id={data.id} size={22} floating={false} />
          </View>
        </View>

        <View style={styles.panel}>
          <View style={styles.row}>
            <Text style={styles.badge}>{tEnum("propertyType", data.property_type)}</Text>
            <Text style={styles.badge}>{tEnum("contract", data.contract)}</Text>
            {data.status === "reserved" ? (
              <Text style={[styles.badge, styles.badgeWarning]}>{t("property.reserved")}</Text>
            ) : null}
          </View>
          <Heading size="xxl">{data.title}</Heading>
          <View style={styles.row}>
            <Ionicons name="location-outline" size={16} color={colors.gray500} />
            <Body muted>{where}</Body>
          </View>
          <Text style={styles.price}>{price}</Text>

          <View style={styles.facts}>
            {data.rooms ? (
              <Fact
                icon="grid-outline"
                label={tCount(data.rooms, "property.room", "property.rooms")}
              />
            ) : null}
            {data.bedrooms ? (
              <Fact
                icon="bed-outline"
                label={tCount(data.bedrooms, "property.bedroom", "property.bedrooms")}
              />
            ) : null}
            {data.bathrooms ? (
              <Fact
                icon="water-outline"
                label={tCount(data.bathrooms, "property.bathroom", "property.bathrooms")}
              />
            ) : null}
            <Fact icon="resize-outline" label={t("common.sqm", { value: data.surface_sqm })} />
          </View>

          {data.description ? (
            <View style={styles.section}>
              <Heading size="lg">{t("property.description")}</Heading>
              <Body>{data.description}</Body>
            </View>
          ) : null}

          {data.features.length ? (
            <View style={styles.section}>
              <Heading size="lg">{t("property.features")}</Heading>
              <View style={styles.featureList}>
                {data.features.map((feature) => (
                  <View key={feature} style={styles.feature}>
                    <Ionicons name="checkmark-circle" size={18} color={colors.brandBlue} />
                    <Body>{tEnum("feature", feature)}</Body>
                  </View>
                ))}
              </View>
            </View>
          ) : null}

          {details.length ? (
            <View style={styles.section}>
              <Heading size="lg">{t("property.details")}</Heading>
              {details.map(([label, value]) => (
                <DetailRow key={label} label={label} value={value} />
              ))}
            </View>
          ) : null}

          <Body muted>{reference}</Body>
        </View>
      </ScrollView>

      {/* Quick contact is always reachable from a property (CLAUDE.md, section 13). */}
      <View style={[styles.contactBar, { paddingBottom: Math.max(insets.bottom, spacing.lg) }]}>
        <Button
          label={t("property.call")}
          icon="call"
          onPress={() => void contact.call()}
          style={styles.contactButton}
        />
        <Button
          label={t("property.whatsapp")}
          icon="logo-whatsapp"
          variant="secondary"
          onPress={() =>
            void contact.whatsapp(
              t("property.whatsappMessage", { reference: data.reference, title: data.title }),
            )
          }
          style={styles.contactButton}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("property.email")}
          onPress={() => void contact.email(`${reference} – ${data.title}`)}
          style={styles.mailButton}
        >
          <Ionicons name="mail-outline" size={22} color={colors.brandBlue} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.white },
  missing: { flex: 1, backgroundColor: colors.gray50 },
  counter: {
    position: "absolute",
    right: spacing.lg,
    bottom: spacing.xxl + spacing.md,
    overflow: "hidden",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.overlay,
    color: colors.white,
    fontSize: typography.sizes.xs,
    fontWeight: "600",
  },
  topButtons: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  roundButton: {
    width: 40,
    height: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
    ...cardShadow,
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flexWrap: "wrap" },
  panel: {
    marginTop: -spacing.xxl,
    padding: spacing.xl,
    gap: spacing.md,
    borderTopLeftRadius: radii.lg * 1.5,
    borderTopRightRadius: radii.lg * 1.5,
    backgroundColor: colors.white,
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
  price: { fontSize: typography.sizes.xxl, fontWeight: "700", color: colors.brandBlue },
  facts: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  fact: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: colors.gray50,
  },
  factText: { fontSize: typography.sizes.sm, color: colors.gray900, fontWeight: "500" },
  section: { gap: spacing.sm, marginTop: spacing.md },
  featureList: { gap: spacing.sm },
  feature: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  detailValue: { color: colors.gray900, fontWeight: "500" },
  contactBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    backgroundColor: colors.white,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
  },
  contactButton: { flex: 1 },
  mailButton: {
    width: 48,
    height: 48,
    borderRadius: radii.md,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.gray300,
  },
});
