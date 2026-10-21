import { ApiError } from "@taraborrelli/api-client";
import { useMutation } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text } from "react-native";

import { api } from "../src/api";
import { AuthLayout, useAuthOnDark } from "../src/components/AuthLayout";
import { Field, FormError } from "../src/components/Form";
import { Body, Button, Heading } from "../src/components/ui";
import { t, tError } from "../src/i18n";
import { colors, spacing, typography } from "../src/theme";

type Step = "email" | "code" | "done";

const errorText = (error: unknown): string | null =>
  error ? tError(error instanceof ApiError ? error.code : undefined) : null;

/** "Password dimenticata": email, then the emailed code with the new password. */
export default function ForgotPassword() {
  const onDark = useAuthOnDark();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ code?: string; password?: string }>({});
  const [resent, setResent] = useState(false);

  const request = useMutation({ mutationFn: () => api.auth.forgotPassword(email.trim()) });
  const reset = useMutation({
    mutationFn: () => api.auth.resetPassword(email.trim(), code.trim(), password),
    onSuccess: () => setStep("done"),
  });

  const sendCode = () =>
    request.mutate(undefined, {
      onSuccess: () => {
        if (step === "code") setResent(true);
        setStep("code");
      },
    });

  const save = () => {
    const errors: { code?: string; password?: string } = {};
    if (!/^\d{6}$/.test(code.trim())) errors.code = t("forgot.invalidCode");
    if (password.length < 10) errors.password = t("auth.shortPassword");
    setFieldErrors(errors);
    if (Object.keys(errors).length === 0) reset.mutate();
  };

  const textStyle = onDark ? styles.onDark : null;
  const softStyle = onDark ? styles.onDarkSoft : null;
  const backLink = (
    <Pressable
      accessibilityRole="link"
      onPress={() => router.replace("/accedi")}
      style={styles.link}
    >
      <Text style={[styles.linkText, textStyle]}>{t("forgot.backToLogin")}</Text>
    </Pressable>
  );

  if (step === "done") {
    return (
      <AuthLayout>
        <Heading size="xxl" style={textStyle}>
          {t("forgot.doneTitle")}
        </Heading>
        <Body style={softStyle}>{t("forgot.doneSubtitle")}</Body>
        <Button
          label={t("auth.login")}
          onPress={() => router.replace("/accedi")}
          variant={onDark ? "light" : "primary"}
        />
      </AuthLayout>
    );
  }

  if (step === "code") {
    return (
      <AuthLayout>
        <Heading size="xxl" style={textStyle}>
          {t("forgot.codeTitle")}
        </Heading>
        <Body style={softStyle}>{t("forgot.codeSubtitle", { email: email.trim() })}</Body>
        <FormError message={errorText(reset.error)} />
        {resent ? <Body style={softStyle}>{t("forgot.resent")}</Body> : null}
        <Field
          label={t("forgot.code")}
          value={code}
          onChangeText={setCode}
          keyboardType="number-pad"
          maxLength={6}
          autoComplete="one-time-code"
          textContentType="oneTimeCode"
          error={fieldErrors.code}
          onDark={onDark}
        />
        <Field
          label={t("forgot.newPassword")}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="new-password"
          textContentType="newPassword"
          hint={t("auth.passwordHint")}
          error={fieldErrors.password}
          onDark={onDark}
          onSubmitEditing={save}
        />
        <Button
          label={reset.isPending ? t("forgot.saving") : t("forgot.save")}
          onPress={save}
          busy={reset.isPending}
          variant={onDark ? "light" : "primary"}
        />
        <Pressable
          accessibilityRole="button"
          onPress={sendCode}
          disabled={request.isPending}
          style={styles.link}
        >
          <Text style={[styles.linkText, textStyle]}>{t("forgot.resend")}</Text>
        </Pressable>
        {backLink}
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <Heading size="xxl" style={textStyle}>
        {t("forgot.title")}
      </Heading>
      <Body style={softStyle}>{t("forgot.subtitle")}</Body>
      <FormError message={errorText(request.error)} />
      <Field
        label={t("auth.email")}
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        autoComplete="email"
        textContentType="emailAddress"
        onDark={onDark}
        onSubmitEditing={sendCode}
      />
      <Button
        label={request.isPending ? t("forgot.sending") : t("forgot.send")}
        onPress={sendCode}
        busy={request.isPending}
        disabled={!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())}
        variant={onDark ? "light" : "primary"}
      />
      {backLink}
    </AuthLayout>
  );
}

const styles = StyleSheet.create({
  link: { alignItems: "center", padding: spacing.md },
  linkText: { color: colors.brandBlue, fontWeight: "600", fontSize: typography.sizes.md },
  onDark: { color: colors.white },
  onDarkSoft: { color: colors.brandLightBlueSoft, fontSize: typography.sizes.lg },
});
