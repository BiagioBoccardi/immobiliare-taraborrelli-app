import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { PropertyCard } from "../../src/components/PropertyCard";
import { Screen } from "../../src/components/Screen";
import { Body, Button, Card, EmptyState, Heading, Loading } from "../../src/components/ui";
import { useFavorites } from "../../src/favorites";
import { t } from "../../src/i18n";
import { useGrid } from "../../src/layout";
import { isNotFound, useFavoriteProperties } from "../../src/queries";
import { colors, spacing, typography } from "../../src/theme";

export default function Favorites() {
  const { ids, ready, remove } = useFavorites();
  const results = useFavoriteProperties(ids);
  const grid = useGrid();
  const cell = grid.itemWidth ? { width: grid.itemWidth } : null;

  return (
    <Screen>
      <Heading size="xxl">{t("favorites.title")}</Heading>
      {!ready ? <Loading /> : null}
      {ready && ids.length === 0 ? (
        <EmptyState
          icon="heart-outline"
          title={t("favorites.empty")}
          hint={t("favorites.emptyHint")}
          action={
            <Button
              label={t("home.actionSearch")}
              icon="search"
              onPress={() => router.navigate("/cerca")}
            />
          }
        />
      ) : null}
      <View style={grid.columns > 1 ? styles.grid : styles.list}>
        {ids.map((id, index) => {
          const result = results[index];
          if (!result || result.isPending) {
            return (
              <View key={id} style={cell}>
                <Loading />
              </View>
            );
          }
          if (result.data) {
            return (
              <View key={id} style={cell}>
                <PropertyCard property={result.data} />
              </View>
            );
          }
          // Sold or withdrawn properties disappear from the catalog: let the user remove them.
          return (
            <Card key={id} style={[styles.unavailable, cell]}>
              <Text style={styles.unavailableText}>{t("favorites.unavailable")}</Text>
              {isNotFound(result.error) ? null : <Body muted>{t("common.error")}</Body>}
              <Button
                label={t("favorites.remove")}
                variant="secondary"
                onPress={() => remove(id)}
              />
            </Card>
          );
        })}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { gap: spacing.xl },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.lg },
  unavailable: { gap: spacing.md },
  unavailableText: { fontSize: typography.sizes.md, fontWeight: "600", color: colors.gray700 },
});
