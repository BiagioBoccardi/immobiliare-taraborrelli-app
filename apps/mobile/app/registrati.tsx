import { ApiError } from "@taraborrelli/api-client";
import { router } from "expo-router";
import { useState } from "react";
import { Linking, Pressable, StyleSheet, Text } from "react-native";

import {
  EMPTY_REGISTER_FORM,
  toRegisterIn,
  validateRegister,
  type RegisterErrors,
  type RegisterForm,
} from "../src/authForms";
import { AuthLayout, useAuthOnDark } from "../src/components/AuthLayout";
import { Checkbox, Field, FormError } from "../src/components/Form";
import { Body, Button, Heading } from "../src/components/ui";
import { privacy } from "../src/config";
import { t, tError } from "../src/i18n";
import { useSessionStore } from "../src/session";
import { colors, spacing, typography } from "../src/theme";

export default function Register() {
  const session = useSessionStore();
  const onDark = useAuthOnDark();
  const [form, setForm] = useState<RegisterForm>(EMPTY_REGISTER_FORM);
  const [errors, setErrors] = useState<RegisterErrors>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (changes: Partial<RegisterForm>) =>
    setForm((current) => ({ ...current, ...changes }));

  const submit = async () => {
    const found = validateRegister(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    setError(null);
    try {
      await session.register(toRegisterIn(form));
      router.replace("/");
    } catch (caught) {
      setError(tError(caught instanceof ApiError ? caught.code : undefined));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout>
      <Heading size={onDark ? "display" : "xxl"} style={onDark && styles.onDark}>
        {t("auth.registerTitle")}
      </Heading>
      <Body style={onDark && styles.onDarkSoft}>{t("auth.registerSubtitle")}</Body>
      <FormError message={error} />
      <Field
        label={t("auth.name")}
        value={form.fullName}
        onChangeText={(fullName) => set({ fullName })}
        autoComplete="name"
        textContentType="name"
        error={errors.fullName}
        onDark={onDark}
      />
      <Field
        label={t("auth.email")}
        value={form.email}
        onChangeText={(email) => set({ email })}
        keyboardType="email-address"
        autoCapitalize="none"
        autoComplete="email"
        textContentType="emailAddress"
        error={errors.email}
        onDark={onDark}
      />
      <Field
        label={t("auth.password")}
        value={form.password}
        onChangeText={(password) => set({ password })}
        secureTextEntry
        autoComplete="new-password"
        textContentType="newPassword"
        hint={t("auth.passwordHint")}
        error={errors.password}
        onDark={onDark}
      />
      <Checkbox
        checked={form.privacyAccepted}
        label={t("auth.privacy")}
        onToggle={() => set({ privacyAccepted: !form.privacyAccepted })}
        error={errors.privacyAccepted}
        onDark={onDark}
      />
      {privacy.url ? (
        <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(privacy.url)}>
          <Text style={[styles.link, onDark && styles.onDark]}>{t("sell.privacyLink")}</Text>
        </Pressable>
      ) : null}
      <Checkbox
        checked={form.marketingAccepted}
        label={t("auth.marketing")}
        onToggle={() => set({ marketingAccepted: !form.marketingAccepted })}
        onDark={onDark}
      />
      <Button
        label={busy ? t("auth.registering") : t("auth.register")}
        onPress={() => void submit()}
        busy={busy}
        variant={onDark ? "light" : "primary"}
        size={onDark ? "lg" : "md"}
      />
      <Pressable
        accessibilityRole="link"
        onPress={() => router.replace("/accedi")}
        style={styles.switch}
      >
        <Text style={[styles.link, onDark && styles.onDark]}>{t("auth.haveAccount")}</Text>
      </Pressable>
    </AuthLayout>
  );
}

const styles = StyleSheet.create({
  switch: { alignItems: "center", padding: spacing.md },
  link: { color: colors.brandBlue, fontWeight: "600", fontSize: typography.sizes.md },
  onDark: { color: colors.white },
  onDarkSoft: { color: colors.brandLightBlueSoft, fontSize: typography.sizes.lg },
});
