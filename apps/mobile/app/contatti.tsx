import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { images } from "../src/assets";
import { Body, Button, Heading } from "../src/components/ui";
import { agency } from "../src/config";
import { contact } from "../src/contact";
import { t } from "../src/i18n";
import { colors, spacing } from "../src/theme";

export default function Contact() {
  return (
    <SafeAreaView style={styles.safe}>
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
      <View style={styles.content}>
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
            label={`${t("contact.call")} ${agency.phoneLabel}`}
            icon="call"
            onPress={() => void contact.call()}
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
        <Body muted>{agency.email}</Body>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.white },
  top: { padding: spacing.lg, alignItems: "flex-end" },
  content: { flex: 1, alignItems: "center", padding: spacing.xl, gap: spacing.lg },
  logo: { width: 200, aspectRatio: 868 / 480, marginBottom: spacing.md },
  buttons: { alignSelf: "stretch", gap: spacing.md, marginTop: spacing.md },
  center: { textAlign: "center" },
});
