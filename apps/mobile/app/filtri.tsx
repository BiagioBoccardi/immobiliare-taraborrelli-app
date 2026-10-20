import { Ionicons } from "@expo/vector-icons";
import type { Feature, PropertyType, TenantType } from "@taraborrelli/api-client";
import { router } from "expo-router";
import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Body, Button, Chip, Heading, Segmented } from "../src/components/ui";
import { desktopPanel, useLayout } from "../src/layout";
import { t, tEnum } from "../src/i18n";
import { DEFAULT_FILTERS, useSearch, type SearchFilters } from "../src/search";
import { colors, radii, spacing, typography } from "../src/theme";

const TYPES: PropertyType[] = [
  "apartment",
  "house",
  "villa",
  "attic",
  "commercial",
  "land",
  "garage",
  "other",
];
const FEATURES: Feature[] = [
  "elevator",
  "parking",
  "garage",
  "garden",
  "terrace",
  "balcony",
  "cellar",
  "furnished",
  "air_conditioning",
  "autonomous_heating",
];
const TENANTS: TenantType[] = ["students", "workers", "families"];
const ROOMS = [1, 2, 3, 4, 5];

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

/** Filters are edited on a draft and applied all together with "Applica". */
export default function Filters() {
  const { isDesktop } = useLayout();
  const { filters, setFilters } = useSearch();
  const [draft, setDraft] = useState<SearchFilters>(filters);
  const set = (changes: Partial<SearchFilters>) =>
    setDraft((current) => ({ ...current, ...changes }));

  return (
    <SafeAreaView style={[styles.safe, isDesktop && desktopPanel]}>
      <View style={styles.top}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
          onPress={() => router.back()}
          hitSlop={8}
        >
          <Ionicons name="close" size={26} color={colors.gray900} />
        </Pressable>
        <Heading size="xl">{t("filters.title")}</Heading>
        <View style={{ width: 26 }} />
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Section title={t("filters.contract")}>
          <Segmented
            options={[
              { value: "sale", label: t("enum.contract.sale") },
              { value: "rent", label: t("enum.contract.rent") },
            ]}
            value={draft.contract}
            onChange={(contract) => set({ contract })}
          />
        </Section>
        <Section title={t("filters.type")}>
          <View style={styles.wrap}>
            {TYPES.map((type) => (
              <Chip
                key={type}
                label={tEnum("propertyType", type)}
                selected={draft.propertyTypes.includes(type)}
                onPress={() => set({ propertyTypes: toggle(draft.propertyTypes, type) })}
              />
            ))}
          </View>
        </Section>
        <Section title={t("filters.price")}>
          <View style={styles.row}>
            <TextInput
              accessibilityLabel={t("filters.priceMin")}
              placeholder={t("filters.priceMin")}
              placeholderTextColor={colors.gray500}
              keyboardType="number-pad"
              value={draft.priceMin}
              onChangeText={(priceMin) => set({ priceMin })}
              style={styles.input}
            />
            <TextInput
              accessibilityLabel={t("filters.priceMax")}
              placeholder={t("filters.priceMax")}
              placeholderTextColor={colors.gray500}
              keyboardType="number-pad"
              value={draft.priceMax}
              onChangeText={(priceMax) => set({ priceMax })}
              style={styles.input}
            />
          </View>
        </Section>
        <Section title={t("filters.rooms")}>
          <View style={styles.wrap}>
            <Chip
              label={t("filters.roomsAny")}
              selected={draft.roomsMin === null}
              onPress={() => set({ roomsMin: null })}
            />
            {ROOMS.map((rooms) => (
              <Chip
                key={rooms}
                label={`${rooms}+`}
                selected={draft.roomsMin === rooms}
                onPress={() => set({ roomsMin: rooms })}
              />
            ))}
          </View>
        </Section>
        {draft.contract === "rent" ? (
          <Section title={t("filters.tenant")}>
            <View style={styles.wrap}>
              {TENANTS.map((tenant) => (
                <Chip
                  key={tenant}
                  label={tEnum("tenantType", tenant)}
                  selected={draft.tenantType === tenant}
                  onPress={() => set({ tenantType: draft.tenantType === tenant ? null : tenant })}
                />
              ))}
            </View>
          </Section>
        ) : null}
        <Section title={t("filters.features")}>
          <View style={styles.wrap}>
            {FEATURES.map((feature) => (
              <Chip
                key={feature}
                label={tEnum("feature", feature)}
                selected={draft.features.includes(feature)}
                onPress={() => set({ features: toggle(draft.features, feature) })}
              />
            ))}
          </View>
        </Section>
      </ScrollView>
      <View style={styles.footer}>
        <Button
          label={t("filters.reset")}
          variant="secondary"
          onPress={() => setDraft({ ...DEFAULT_FILTERS, contract: draft.contract })}
          style={styles.footerButton}
        />
        <Button
          label={t("filters.apply")}
          onPress={() => {
            setFilters(draft);
            router.back();
          }}
          style={styles.footerButton}
        />
      </View>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <Body style={styles.sectionTitle}>{title}</Body>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.gray50 },
  top: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
  },
  content: { padding: spacing.xl, gap: spacing.xl },
  section: { gap: spacing.md },
  sectionTitle: { fontWeight: "600", color: colors.gray900, fontSize: typography.sizes.md },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  row: { flexDirection: "row", gap: spacing.md },
  input: {
    flex: 1,
    height: 48,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.gray300,
    backgroundColor: colors.white,
    fontSize: typography.sizes.md,
    color: colors.gray900,
  },
  footer: {
    flexDirection: "row",
    gap: spacing.md,
    padding: spacing.xl,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
    backgroundColor: colors.white,
  },
  footerButton: { flex: 1 },
});
