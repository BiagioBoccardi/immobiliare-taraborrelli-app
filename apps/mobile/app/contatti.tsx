import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { images } from "../src/assets";
import { Body, Button, Card, Heading, type IconName } from "../src/components/ui";
import { agency } from "../src/config";
import { contact } from "../src/contact";
import { desktopPanel, useLayout } from "../src/layout";
import { t } from "../src/i18n";
import { colors, spacing, typography } from "../src/theme";

/** One line of the agency's contact details: icon, label and the value (tappable). */
function DetailRow({
  icon,
  label,
  value,
  onPress,
}: {
  icon: IconName;
  label: string;
  value: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${label}: ${value}`}
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
    >
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={18} color={colors.brandBlue} />
      </View>
      <View style={styles.rowText}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowValue} selectable>
          {value}
        </Text>
      </View>
    </Pressable>
  );
}

export default function Contact() {
  const { isDesktop } = useLayout();
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
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Image
          source={images.logo}
          style={styles.logo}
          contentFit="contain"
          accessibilityLabel={agency.name}
        />
        <Heading size="xxl">{t("contact.title")}</Heading>
        <Body style={styles.center}>{t("contact.subtitle")}</Body>
        <View style={styles.buttons}>
          <Button
            label={t("contact.callOffice")}
            icon="call"
            onPress={() => void contact.call(agency.phone)}
          />
          <Button
            label={t("contact.callMobile")}
            icon="phone-portrait-outline"
            variant="secondary"
            onPress={() => void contact.call(agency.mobile)}
          />
          <Button
            label={t("contact.whatsapp")}
            icon="logo-whatsapp"
            variant="secondary"
            onPress={() => void contact.whatsapp(t("contact.whatsappMessage"))}
          />
          <Button
            label={t("contact.email")}
            icon="mail-outline"
            variant="secondary"
            onPress={() => void contact.email(agency.name)}
          />
        </View>
        <Card style={styles.details}>
          <Text style={styles.detailsTitle}>{t("contact.details")}</Text>
          <DetailRow
            icon="mail-outline"
            label={t("contact.emailLabel")}
            value={agency.email}
            onPress={() => void contact.email(agency.name)}
          />
          <DetailRow
            icon="call-outline"
            label={t("contact.landline")}
            value={agency.phoneLabel}
            onPress={() => void contact.call(agency.phone)}
          />
          <DetailRow
            icon="phone-portrait-outline"
            label={t("contact.mobile")}
            value={agency.mobileLabel}
            onPress={() => void contact.call(agency.mobile)}
          />
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.white },
  top: { paddingHorizontal: spacing.lg, paddingTop: spacing.lg, alignItems: "flex-end" },
  content: { alignItems: "center", padding: spacing.xl, gap: spacing.lg },
  logo: { width: 200, aspectRatio: 868 / 480, marginBottom: spacing.md },
  buttons: { alignSelf: "stretch", gap: spacing.md, marginTop: spacing.md },
  center: { textAlign: "center" },
  details: { alignSelf: "stretch", gap: spacing.xs, marginTop: spacing.sm },
  detailsTitle: {
    fontSize: typography.sizes.sm,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  rowPressed: { opacity: 0.6 },
  rowIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.brandLightBlueSoft,
  },
  rowText: { flex: 1 },
  rowLabel: { fontSize: typography.sizes.xs, color: colors.gray500 },
  // Small enough for the full email address to fit on one line on a phone.
  rowValue: { fontSize: typography.sizes.sm, color: colors.gray900, fontWeight: "500" },
});
