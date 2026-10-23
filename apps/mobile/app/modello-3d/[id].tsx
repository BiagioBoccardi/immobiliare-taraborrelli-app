import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ModelViewer } from "../../src/components/ModelViewer";
import { Body, EmptyState, ErrorState, Heading, Loading } from "../../src/components/ui";
import { t } from "../../src/i18n";
import { isNotFound, useProperty } from "../../src/queries";
import { colors, radii, spacing } from "../../src/theme";

export default function ThreeDModelScreen() {
  const { id = "" } = useLocalSearchParams<{ id: string }>();
  const property = useProperty(id);
  const goBack = () => (router.canGoBack() ? router.back() : router.replace(`/immobile/${id}`));

  let content;
  if (property.isPending) {
    content = <Loading />;
  } else if (property.isError && !isNotFound(property.error)) {
    content = <ErrorState onRetry={() => void property.refetch()} />;
  } else if (!property.data?.three_d_model) {
    content = <EmptyState icon="cube-outline" title={t("model3d.missing")} />;
  } else {
    content = (
      <ModelViewer
        url={property.data.three_d_model.url}
        label={property.data.title}
        errorText={t("model3d.loadError")}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
          onPress={goBack}
          hitSlop={8}
          style={styles.back}
        >
          <Ionicons name="chevron-back" size={22} color={colors.gray900} />
        </Pressable>
        <View style={styles.titles}>
          <Heading size="lg">{t("model3d.title")}</Heading>
          {property.data ? <Body muted>{property.data.title}</Body> : null}
        </View>
      </View>
      <View style={styles.viewer}>{content}</View>
      {property.data?.three_d_model ? (
        <View style={styles.hint}>
          <Ionicons name="hand-left-outline" size={16} color={colors.gray500} />
          <Body muted>{t("model3d.hint")}</Body>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.gray50 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
  },
  back: {
    width: 40,
    height: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
  },
  titles: { flex: 1 },
  viewer: { flex: 1 },
  hint: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    padding: spacing.lg,
  },
});
