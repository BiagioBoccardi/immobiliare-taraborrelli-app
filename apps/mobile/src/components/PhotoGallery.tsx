import { Ionicons } from "@expo/vector-icons";
import type { PropertyDetail } from "@taraborrelli/api-client";
import { Image } from "expo-image";
import { router } from "expo-router";
import { useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";

import { photosToLoad } from "../gallery";
import { t } from "../i18n";
import { cardShadow, colors, radii, spacing, typography } from "../theme";

/** Dots are shown up to this many photos; with more, the counter is enough. */
const MAX_DOTS = 12;

/**
 * Photos of a property: swipe on phones, arrows and dots with the mouse in the browser.
 * The index follows the scroll position, so it stays right however the user moves.
 */
export function PhotoGallery({
  property,
  width,
  rounded = false,
}: {
  property: PropertyDetail;
  width: number;
  rounded?: boolean;
}) {
  const height = rounded ? width * 0.62 : width * 0.85;
  const photos = property.photos;
  const [index, setIndex] = useState(0);
  // Photos stay loaded once downloaded, so going back never shows an empty frame.
  const [loaded, setLoaded] = useState<Set<number>>(() =>
    photosToLoad(new Set(), 0, photos.length),
  );
  const list = useRef<FlatList<PropertyDetail["photos"][number]>>(null);
  const last = photos.length - 1;

  const show = (current: number) => {
    setIndex(current);
    setLoaded((previous) => photosToLoad(previous, current, photos.length));
  };

  const goTo = (target: number) => {
    const next = Math.max(0, Math.min(last, target));
    list.current?.scrollToOffset({ offset: next * width, animated: true });
    show(next);
  };

  const onScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const current = Math.round(event.nativeEvent.contentOffset.x / width);
    if (current !== index && current >= 0 && current <= last) show(current);
  };

  return (
    <View style={[rounded ? styles.rounded : null, { width, height }]}>
      <FlatList
        ref={list}
        horizontal
        pagingEnabled
        data={photos}
        keyExtractor={(photo) => photo.id}
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
        getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
        // Every page is mounted, so scrolling far ahead never lands on an unrendered page.
        initialNumToRender={photos.length}
        windowSize={photos.length * 2 + 1}
        extraData={loaded}
        renderItem={({ item, index: i }) => (
          <View style={[styles.page, { width, height }]}>
            <ActivityIndicator color={colors.brandBlue} style={styles.spinner} />
            {loaded.has(i) ? (
              <Image
                source={{ uri: item.url }}
                style={StyleSheet.absoluteFill}
                contentFit="cover"
                transition={150}
                priority={i === index ? "high" : "normal"}
                accessibilityLabel={
                  item.caption ?? t("property.photo", { index: i + 1, total: photos.length })
                }
              />
            ) : null}
          </View>
        )}
        ListEmptyComponent={<View style={{ width, height, backgroundColor: colors.gray100 }} />}
      />
      {photos.length > 1 ? (
        <>
          {index > 0 ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("property.previousPhoto")}
              onPress={() => goTo(index - 1)}
              style={[styles.arrow, styles.arrowLeft, { top: height / 2 - 20 }]}
            >
              <Ionicons name="chevron-back" size={22} color={colors.gray900} />
            </Pressable>
          ) : null}
          {index < last ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("property.nextPhoto")}
              onPress={() => goTo(index + 1)}
              style={[styles.arrow, styles.arrowRight, { top: height / 2 - 20 }]}
            >
              <Ionicons name="chevron-forward" size={22} color={colors.gray900} />
            </Pressable>
          ) : null}
          {photos.length <= MAX_DOTS ? (
            <View style={[styles.dots, rounded ? styles.dotsRounded : null]}>
              {photos.map((photo, i) => (
                <Pressable
                  key={photo.id}
                  accessibilityRole="button"
                  accessibilityLabel={t("property.photo", { index: i + 1, total: photos.length })}
                  accessibilityState={{ selected: i === index }}
                  onPress={() => goTo(i)}
                  hitSlop={6}
                  style={[styles.dot, i === index && styles.dotActive]}
                />
              ))}
            </View>
          ) : null}
          <Text style={[styles.counter, rounded ? styles.counterRounded : null]}>
            {index + 1}/{photos.length}
          </Text>
        </>
      ) : null}
      {photos[index]?.three_d_url ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("property.photo3d")}
          onPress={() =>
            router.push({
              pathname: "/modello-3d/[id]",
              params: { id: property.id, foto: photos[index]?.id ?? "" },
            })
          }
          style={[styles.threeD, rounded ? styles.threeDRounded : null]}
        >
          <Ionicons name="cube-outline" size={16} color={colors.white} />
          <Text style={styles.threeDText}>3D</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  rounded: { borderRadius: radii.lg, overflow: "hidden" },
  page: { alignItems: "center", justifyContent: "center", backgroundColor: colors.gray100 },
  spinner: { position: "absolute" },
  arrow: {
    position: "absolute",
    width: 40,
    height: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
    opacity: 0.92,
    ...cardShadow,
  },
  arrowLeft: { left: spacing.md },
  arrowRight: { right: spacing.md },
  // Above the rounded panel that overlaps the photo on phones.
  dots: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: spacing.xxl + spacing.md,
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.xs,
  },
  dotsRounded: { bottom: spacing.lg },
  dot: {
    width: 8,
    height: 8,
    borderRadius: radii.pill,
    backgroundColor: colors.white,
    opacity: 0.6,
  },
  dotActive: { width: 20, opacity: 1 },
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
  counterRounded: { bottom: spacing.md },
  // The room in the current photo can be opened in 3D.
  threeD: {
    position: "absolute",
    left: spacing.lg,
    bottom: spacing.xxl + spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.brandBlue,
  },
  threeDRounded: { bottom: spacing.md },
  threeDText: { color: colors.white, fontSize: typography.sizes.xs, fontWeight: "700" },
});
