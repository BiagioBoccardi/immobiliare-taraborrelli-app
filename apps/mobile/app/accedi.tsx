import { ApiError } from "@taraborrelli/api-client";
import { Image } from "expo-image";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text } from "react-native";

import { images } from "../src/assets";
import { AuthLayout, useAuthOnDark } from "../src/components/AuthLayout";
import { Field, FormError } from "../src/components/Form";
import { Body, Button, Heading } from "../src/components/ui";
import { t, tError } from "../src/i18n";
import { useSessionStore } from "../src/session";
import { colors, spacing, typography } from "../src/theme";

export default function Login() {
  const session = useSessionStore();
  const onDark = useAuthOnDark();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await session.login(email.trim(), password);
      router.replace("/");
    } catch (caught) {
      setError(tError(caught instanceof ApiError ? caught.code : undefined));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout>
      <Image
        source={onDark ? images.logoWhite : images.logo}
        style={styles.logo}
        contentFit="contain"
        accessibilityLabel="Logo"
      />
      <Heading size="xxl" style={onDark && styles.onDark}>
        {t("auth.loginTitle")}
      </Heading>
      <Body style={onDark && styles.onDarkSoft}>{t("auth.loginSubtitle")}</Body>
      <FormError message={error} />
      <Field
        label={t("auth.email")}
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        autoComplete="email"
        textContentType="username"
        onDark={onDark}
      />
      <Field
        label={t("auth.password")}
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoComplete="current-password"
        textContentType="password"
        onSubmitEditing={() => void submit()}
        onDark={onDark}
      />
      <Button
        label={busy ? t("auth.loggingIn") : t("auth.login")}
        onPress={() => void submit()}
        busy={busy}
        disabled={!email || !password}
        variant={onDark ? "light" : "primary"}
      />
      <Pressable
        accessibilityRole="link"
        onPress={() => router.replace("/registrati")}
        style={styles.switch}
      >
        <Text style={[styles.link, onDark && styles.onDark]}>{t("auth.noAccount")}</Text>
      </Pressable>
    </AuthLayout>
  );
}

const styles = StyleSheet.create({
  logo: { width: 180, aspectRatio: 868 / 480, alignSelf: "center", marginVertical: spacing.xl },
  switch: { alignItems: "center", padding: spacing.md },
  link: { color: colors.brandBlue, fontWeight: "600", fontSize: typography.sizes.md },
  onDark: { color: colors.white },
  onDarkSoft: { color: colors.brandLightBlueSoft },
});
