import { Image } from "expo-image";
import { router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { images } from "../src/assets";
import { Button } from "../src/components/ui";
import { useLayout } from "../src/layout";
import { t } from "../src/i18n";
import { markOnboardingSeen } from "../src/onboarding";
import { colors, fonts, spacing, typography } from "../src/theme";

/** First launch: full-screen brand welcome with a single "Inizia" button. */
export default function Welcome() {
  const { isDesktop } = useLayout();
  const start = async () => {
    await markOnboardingSeen();
    router.replace("/");
  };

  return (
    <View style={styles.screen}>
      <StatusBar style="light" />
      <SafeAreaView style={[styles.content, isDesktop && styles.contentDesktop]}>
        <Image
          source={images.logoWhite}
          style={[styles.logo, isDesktop && styles.logoDesktop]}
          contentFit="contain"
          accessibilityLabel={t("onboarding.title")}
        />
        <View style={styles.texts}>
          <Text style={styles.title}>{t("onboarding.title")}</Text>
          <Text style={styles.subtitle}>{t("onboarding.subtitle")}</Text>
        </View>
        <Button label={t("onboarding.start")} variant="light" onPress={start} />
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.brandBlue },
  content: {
    flex: 1,
    justifyContent: "space-between",
    padding: spacing.xxl,
    gap: spacing.xxl,
  },
  // On desktop: the whole window in blue, with a centered column of readable width.
  contentDesktop: {
    width: "100%",
    maxWidth: 560,
    alignSelf: "center",
    justifyContent: "center",
    gap: spacing.xxxl,
  },
  logoDesktop: { width: 320, height: (320 * 480) / 868, marginTop: 0 },
  logo: { width: "80%", aspectRatio: 868 / 480, alignSelf: "center", marginTop: spacing.xxxl },
  texts: { gap: spacing.lg },
  title: {
    fontFamily: fonts.heading,
    fontSize: typography.sizes.display,
    lineHeight: typography.sizes.display * 1.15,
    color: colors.white,
  },
  subtitle: {
    fontSize: typography.sizes.md,
    lineHeight: typography.sizes.md * typography.lineHeight,
    color: colors.brandLightBlueSoft,
  },
});
