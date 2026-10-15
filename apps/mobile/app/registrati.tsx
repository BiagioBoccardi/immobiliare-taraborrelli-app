import { ApiError } from "@taraborrelli/api-client";
import { router } from "expo-router";
import { useState } from "react";
import {
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  EMPTY_REGISTER_FORM,
  toRegisterIn,
  validateRegister,
  type RegisterErrors,
  type RegisterForm,
} from "../src/authForms";
import { Checkbox, Field, FormError } from "../src/components/Form";
import { Body, Button, Heading } from "../src/components/ui";
import { privacy } from "../src/config";
import { t, tError } from "../src/i18n";
import { useSessionStore } from "../src/session";
import { colors, spacing, typography } from "../src/theme";

export default function Register() {
  const session = useSessionStore();
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
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.flex}
      >
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Heading size="xxl">{t("auth.registerTitle")}</Heading>
          <Body>{t("auth.registerSubtitle")}</Body>
          <FormError message={error} />
          <Field
            label={t("auth.name")}
            value={form.fullName}
            onChangeText={(fullName) => set({ fullName })}
            autoComplete="name"
            textContentType="name"
            error={errors.fullName}
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
          />
          <Checkbox
            checked={form.privacyAccepted}
            label={t("auth.privacy")}
            onToggle={() => set({ privacyAccepted: !form.privacyAccepted })}
            error={errors.privacyAccepted}
          />
          {privacy.url ? (
            <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(privacy.url)}>
              <Text style={styles.link}>{t("sell.privacyLink")}</Text>
            </Pressable>
          ) : null}
          <Checkbox
            checked={form.marketingAccepted}
            label={t("auth.marketing")}
            onToggle={() => set({ marketingAccepted: !form.marketingAccepted })}
          />
          <Button
            label={busy ? t("auth.registering") : t("auth.register")}
            onPress={() => void submit()}
            busy={busy}
          />
          <Pressable
            accessibilityRole="link"
            onPress={() => router.replace("/accedi")}
            style={styles.switch}
          >
            <Text style={styles.link}>{t("auth.haveAccount")}</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.white },
  flex: { flex: 1 },
  content: { padding: spacing.xl, gap: spacing.lg },
  switch: { alignItems: "center", padding: spacing.md },
  link: { color: colors.brandBlue, fontWeight: "600", fontSize: typography.sizes.md },
});
