import { Ionicons } from "@expo/vector-icons";
import Constants from "expo-constants";
import { router } from "expo-router";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { Screen } from "../../src/components/Screen";
import { Body, Card, Heading, type IconName } from "../../src/components/ui";
import { privacy } from "../../src/config";
import { t } from "../../src/i18n";
import { colors, spacing, typography } from "../../src/theme";

function Row({ icon, label, onPress }: { icon: IconName; label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.row}>
      <Ionicons name={icon} size={22} color={colors.brandBlue} />
      <Text style={styles.rowText}>{label}</Text>
      <Ionicons name="chevron-forward" size={20} color={colors.gray300} />
    </Pressable>
  );
}

export default function Profile() {
  return (
    <Screen>
      <Heading size="xxl">{t("profile.title")}</Heading>
      <Card style={styles.area}>
        <Ionicons name="person-circle-outline" size={48} color={colors.brandLightBlue} />
        <Heading size="lg">{t("profile.areaTitle")}</Heading>
        <Body>{t("profile.areaBody")}</Body>
      </Card>
      <Card style={styles.list}>
        <Row
          icon="call-outline"
          label={t("profile.contact")}
          onPress={() => router.push("/contatti")}
        />
        {privacy.url ? (
          <Row
            icon="shield-checkmark-outline"
            label={t("profile.privacy")}
            onPress={() => void Linking.openURL(privacy.url)}
          />
        ) : null}
      </Card>
      <View style={styles.version}>
        <Body muted>{t("profile.version", { version: Constants.expoConfig?.version ?? "" })}</Body>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  area: { gap: spacing.sm, alignItems: "flex-start" },
  list: { paddingVertical: spacing.xs },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.md },
  rowText: { flex: 1, fontSize: typography.sizes.md, color: colors.gray900 },
  version: { alignItems: "center" },
});
