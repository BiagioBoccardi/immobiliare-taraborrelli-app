import { Ionicons } from "@expo/vector-icons";
import type { PropertyType } from "@taraborrelli/api-client";
import { router } from "expo-router";
import { useMemo, useState } from "react";
import { FlatList, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { PropertyCard } from "../../src/components/PropertyCard";
import { Screen, TAB_BAR_SPACE } from "../../src/components/Screen";
import {
  Body,
  Button,
  Chip,
  EmptyState,
  ErrorState,
  Heading,
  Loading,
  Segmented,
} from "../../src/components/ui";
import { t, tEnum } from "../../src/i18n";
import { useSearchResults } from "../../src/queries";
import { activeFilterCount, toQuery, useSearch } from "../../src/search";
import { cardShadow, colors, radii, spacing, typography } from "../../src/theme";

const CATEGORIES: PropertyType[] = ["apartment", "house", "villa", "attic", "commercial", "land"];

export default function Search() {
  const { filters, update } = useSearch();
  const [text, setText] = useState(filters.municipality);
  const query = useMemo(() => toQuery(filters), [filters]);
  const results = useSearchResults(query);
  const items = results.data?.pages.flatMap((page) => page.items) ?? [];
  const total = results.data?.pages[0]?.total ?? 0;
  const activeFilters = activeFilterCount(filters);
  const singleType = filters.propertyTypes.length === 1 ? filters.propertyTypes[0] : undefined;

  const header = (
    <View style={styles.header}>
      <Heading size="xxl">{t("search.title")}</Heading>
      <Segmented
        options={[
          { value: "sale", label: t("enum.contract.sale") },
          { value: "rent", label: t("enum.contract.rent") },
        ]}
        value={filters.contract}
        onChange={(contract) => update({ contract })}
      />
      <View style={styles.searchRow}>
        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={20} color={colors.gray500} />
          <TextInput
            accessibilityLabel={t("search.placeholder")}
            placeholder={t("search.placeholder")}
            placeholderTextColor={colors.gray500}
            value={text}
            onChangeText={setText}
            onSubmitEditing={() => update({ municipality: text })}
            onBlur={() => update({ municipality: text })}
            returnKeyType="search"
            style={styles.input}
          />
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("search.filters")}
          onPress={() => router.push("/filtri")}
          style={styles.filterButton}
        >
          <Ionicons name="options-outline" size={22} color={colors.white} />
          {activeFilters > 0 ? <Text style={styles.filterCount}>{activeFilters}</Text> : null}
        </Pressable>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chips}
      >
        <Chip
          label={t("search.all")}
          selected={filters.propertyTypes.length === 0}
          onPress={() => update({ propertyTypes: [] })}
        />
        {CATEGORIES.map((type) => (
          <Chip
            key={type}
            label={tEnum("propertyType", type)}
            selected={singleType === type}
            onPress={() => update({ propertyTypes: singleType === type ? [] : [type] })}
          />
        ))}
      </ScrollView>
      {results.data ? (
        <Body muted>{total === 1 ? t("search.oneResult") : t("search.results", { total })}</Body>
      ) : null}
    </View>
  );

  return (
    <Screen scroll={false}>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <PropertyCard property={item} />}
        ListHeaderComponent={header}
        ListEmptyComponent={
          results.isPending ? (
            <Loading />
          ) : results.isError ? (
            <ErrorState onRetry={() => void results.refetch()} />
          ) : (
            <EmptyState
              icon="search-outline"
              title={t("search.empty")}
              hint={t("search.emptyHint")}
              action={
                <Button
                  label={t("home.actionContact")}
                  variant="secondary"
                  icon="call-outline"
                  onPress={() => router.push("/contatti")}
                />
              }
            />
          )
        }
        ListFooterComponent={results.isFetchingNextPage ? <Loading /> : null}
        onEndReached={() => {
          if (results.hasNextPage && !results.isFetchingNextPage) void results.fetchNextPage();
        }}
        onEndReachedThreshold={0.5}
        ItemSeparatorComponent={() => <View style={{ height: spacing.lg }} />}
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.xl, paddingBottom: TAB_BAR_SPACE },
  header: { gap: spacing.lg, marginBottom: spacing.lg },
  searchRow: { flexDirection: "row", gap: spacing.md },
  searchBox: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    height: 52,
    paddingHorizontal: spacing.lg,
    borderRadius: radii.pill,
    backgroundColor: colors.white,
    ...cardShadow,
  },
  input: { flex: 1, fontSize: typography.sizes.md, color: colors.gray900 },
  filterButton: {
    width: 52,
    height: 52,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandBlue,
  },
  filterCount: {
    position: "absolute",
    top: 2,
    right: 2,
    minWidth: 20,
    height: 20,
    borderRadius: radii.pill,
    overflow: "hidden",
    textAlign: "center",
    lineHeight: 20,
    fontSize: typography.sizes.xs,
    fontWeight: "700",
    color: colors.brandBlue,
    backgroundColor: colors.white,
  },
  chips: { gap: spacing.sm, paddingRight: spacing.xl },
});
