import { StyleSheet, Text, View } from "react-native";

import { t } from "../i18n";
import { colors, radii, spacing, typography } from "../theme";

const DELTA = 0.003;

/**
 * In the browser preview react-native-maps is not available: the OpenStreetMap embedded map
 * shows the pin of the found address (it cannot be moved here).
 */
export function AddressMap({
  latitude,
  longitude,
}: {
  latitude: number;
  longitude: number;
  onMove: (latitude: number, longitude: number) => void;
}) {
  const bbox = [longitude - DELTA, latitude - DELTA, longitude + DELTA, latitude + DELTA].join(",");
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${latitude},${longitude}`;
  return (
    <View style={styles.wrapper}>
      <iframe
        title={t("estimate.mapLabel")}
        src={src}
        style={{ border: 0, width: "100%", height: 220, borderRadius: radii.md }}
        loading="lazy"
      />
      <Text style={styles.hint}>{t("estimate.attribution")}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: spacing.xs },
  hint: { fontSize: typography.sizes.xs, color: colors.gray500 },
});
