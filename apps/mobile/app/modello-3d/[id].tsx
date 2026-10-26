import { Ionicons } from "@expo/vector-icons";
import type { PropertyDetail } from "@taraborrelli/api-client";
import { Image } from "expo-image";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ModelViewer } from "../../src/components/ModelViewer";
import { Body, EmptyState, ErrorState, Heading, Loading } from "../../src/components/ui";
import { t } from "../../src/i18n";
import { isNotFound, useProperty } from "../../src/queries";
import { hasThreeD, roomsWithThreeD } from "../../src/threeD";
import { colors, radii, spacing, typography } from "../../src/theme";

function Rooms({
  property,
  initialPhotoId,
}: {
  property: PropertyDetail;
  initialPhotoId?: string;
}) {
  const rooms = roomsWithThreeD(property);
  const start = Math.max(
    0,
    rooms.findIndex((room) => room.id === initialPhotoId),
  );
  const [index, setIndex] = useState(start);
  const room = rooms[index] ?? rooms[0];
  if (!room?.three_d_url) return null;
  const label = room.caption ?? t("model3d.room", { index: index + 1 });

  return (
    <View style={styles.rooms}>
      <View style={styles.viewer}>
        <ModelViewer
          url={room.three_d_url}
          label={label}
          errorText={t("model3d.loadError")}
          mode="room"
        />
        {rooms.length > 1 ? (
          <>
            {index > 0 ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t("model3d.previousRoom")}
                onPress={() => setIndex(index - 1)}
                style={[styles.arrow, styles.arrowLeft]}
              >
                <Ionicons name="chevron-back" size={22} color={colors.gray900} />
              </Pressable>
            ) : null}
            {index < rooms.length - 1 ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t("model3d.nextRoom")}
                onPress={() => setIndex(index + 1)}
                style={[styles.arrow, styles.arrowRight]}
              >
                <Ionicons name="chevron-forward" size={22} color={colors.gray900} />
              </Pressable>
            ) : null}
            <Text style={styles.counter}>
              {index + 1}/{rooms.length}
            </Text>
          </>
        ) : null}
      </View>
      <View style={styles.note}>
        <Body muted>{t("model3d.rebuilt")}</Body>
      </View>
      {rooms.length > 1 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.thumbList}
          contentContainerStyle={styles.thumbs}
        >
          {rooms.map((item, i) => (
            <Pressable
              key={item.id}
              accessibilityRole="button"
              accessibilityLabel={item.caption ?? t("model3d.room", { index: i + 1 })}
              accessibilityState={{ selected: i === index }}
              onPress={() => setIndex(i)}
              style={[styles.thumb, i === index && styles.thumbActive]}
            >
              <Image source={{ uri: item.url }} style={styles.thumbImage} contentFit="cover" />
            </Pressable>
          ))}
        </ScrollView>
      ) : null}
    </View>
  );
}

export default function ThreeDModelScreen() {
  const { id = "", foto } = useLocalSearchParams<{ id: string; foto?: string }>();
  const property = useProperty(id);
  const goBack = () => (router.canGoBack() ? router.back() : router.replace(`/immobile/${id}`));
  const data = property.data;

  let content;
  if (property.isPending) {
    content = <Loading />;
  } else if (property.isError && !isNotFound(property.error)) {
    content = <ErrorState onRetry={() => void property.refetch()} />;
  } else if (data && roomsWithThreeD(data).length > 0) {
    content = <Rooms property={data} {...(foto ? { initialPhotoId: foto } : {})} />;
  } else if (data?.three_d_model) {
    content = (
      <View style={styles.viewer}>
        <ModelViewer
          url={data.three_d_model.url}
          label={data.title}
          errorText={t("model3d.loadError")}
        />
      </View>
    );
  } else {
    content = <EmptyState icon="cube-outline" title={t("model3d.missing")} />;
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
          {data ? <Body muted>{data.title}</Body> : null}
        </View>
      </View>
      <View style={styles.content}>{content}</View>
      {data && hasThreeD(data) ? (
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
  content: { flex: 1 },
  rooms: { flex: 1, gap: spacing.md },
  viewer: { flex: 1 },
  arrow: {
    position: "absolute",
    top: "50%",
    marginTop: -20,
    width: 40,
    height: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
  },
  arrowLeft: { left: spacing.md },
  arrowRight: { right: spacing.md },
  counter: {
    position: "absolute",
    right: spacing.lg,
    bottom: spacing.md,
    overflow: "hidden",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.overlay,
    color: colors.white,
    fontSize: typography.sizes.xs,
    fontWeight: "600",
  },
  note: { paddingHorizontal: spacing.lg },
  thumbList: { flexGrow: 0 },
  thumbs: { gap: spacing.sm, paddingHorizontal: spacing.lg },
  thumb: {
    width: 84,
    height: 56,
    borderRadius: radii.md,
    overflow: "hidden",
    borderWidth: 2,
    borderColor: "transparent",
  },
  thumbActive: { borderColor: colors.brandBlue },
  thumbImage: { width: "100%", height: "100%" },
  hint: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    padding: spacing.lg,
  },
});
