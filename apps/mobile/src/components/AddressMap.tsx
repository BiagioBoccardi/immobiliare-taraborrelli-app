import { StyleSheet, Text, View } from "react-native";
import MapView, { Marker } from "react-native-maps";

import { t } from "../i18n";
import { colors, radii, spacing, typography } from "../theme";

/** Map with the pin of the address: the owner can drag it onto the right building. */
export function AddressMap({
  latitude,
  longitude,
  onMove,
}: {
  latitude: number;
  longitude: number;
  onMove: (latitude: number, longitude: number) => void;
}) {
  return (
    <View style={styles.wrapper}>
      <MapView
        key={`${latitude},${longitude}`}
        style={styles.map}
        initialRegion={{ latitude, longitude, latitudeDelta: 0.004, longitudeDelta: 0.004 }}
        accessibilityLabel={t("estimate.mapLabel")}
      >
        <Marker
          coordinate={{ latitude, longitude }}
          draggable
          pinColor={colors.brandBlue}
          onDragEnd={(event) => {
            const { coordinate } = event.nativeEvent;
            onMove(coordinate.latitude, coordinate.longitude);
          }}
        />
      </MapView>
      <Text style={styles.hint}>{t("estimate.dragPin")}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: spacing.xs },
  map: { height: 220, borderRadius: radii.md, overflow: "hidden" },
  hint: { fontSize: typography.sizes.xs, color: colors.gray500 },
});
