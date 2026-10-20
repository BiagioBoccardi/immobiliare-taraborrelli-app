import { Ionicons } from "@expo/vector-icons";
import type { OwnerIntention } from "@taraborrelli/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Linking,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";

import { Screen } from "../../src/components/Screen";
import { Body, Button, Card, Chip, Heading, Segmented } from "../../src/components/ui";
import { api } from "../../src/api";
import { privacy } from "../../src/config";
import { contact } from "../../src/contact";
import { t, tEnum, type TranslationKey } from "../../src/i18n";
import {
  EMPTY_OWNER_FORM,
  toOwnerRequest,
  validateOwnerForm,
  type OwnerForm,
  type OwnerFormErrors,
  type OwnerPropertyType,
} from "../../src/ownerRequest";
import { useSession } from "../../src/session";
import { colors, radii, spacing, typography } from "../../src/theme";

const TYPES: OwnerPropertyType[] = ["apartment", "house", "villa", "attic", "commercial", "land"];
const INTENTIONS: OwnerIntention[] = ["know_value", "planning", "decided"];
const BENEFITS: TranslationKey[] = ["sell.benefit1", "sell.benefit2", "sell.benefit3"];

function Field({
  label,
  error,
  ...input
}: { label: string; error?: string | undefined } & TextInputProps) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.gray500}
        style={[styles.input, error ? styles.inputError : null]}
        {...input}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

function Checkbox({
  checked,
  label,
  onToggle,
  error,
}: {
  checked: boolean;
  label: string;
  onToggle: () => void;
  error?: string | undefined;
}) {
  return (
    <View>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked }}
        onPress={onToggle}
        style={styles.checkbox}
      >
        <Ionicons
          name={checked ? "checkbox" : "square-outline"}
          size={24}
          color={error ? colors.danger : colors.brandBlue}
        />
        <Text style={styles.checkboxLabel}>{label}</Text>
      </Pressable>
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

export default function Sell() {
  const { user } = useSession();
  const queryClient = useQueryClient();
  // The account already knows the name: one field less to fill in.
  const initialForm: OwnerForm = { ...EMPTY_OWNER_FORM, fullName: user?.full_name ?? "" };
  const [form, setForm] = useState<OwnerForm>(initialForm);
  const [errors, setErrors] = useState<OwnerFormErrors>({});
  const send = useMutation({
    mutationFn: () => api.lead.createOwnerRequest(toOwnerRequest(form)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me", "requests"] }),
  });
  const set = (changes: Partial<OwnerForm>) => setForm((current) => ({ ...current, ...changes }));

  const submit = () => {
    const found = validateOwnerForm(form);
    setErrors(found);
    if (Object.keys(found).length === 0) send.mutate();
  };

  if (send.isSuccess) {
    return (
      <Screen width="narrow" contentStyle={styles.success}>
        <Ionicons name="checkmark-circle" size={64} color={colors.success} />
        <Heading size="xxl" style={styles.center}>
          {t("sell.successTitle")}
        </Heading>
        <Body style={styles.center}>{t("sell.successBody")}</Body>
        <Button
          label={t("sell.another")}
          variant="secondary"
          onPress={() => {
            setForm(initialForm);
            send.reset();
          }}
        />
      </Screen>
    );
  }

  return (
    <Screen width="narrow">
      <View style={styles.intro}>
        <Heading size="xxl">{t("sell.title")}</Heading>
        <Body>{t("sell.subtitle")}</Body>
        {BENEFITS.map((benefit) => (
          <View key={benefit} style={styles.benefit}>
            <Ionicons name="checkmark-circle" size={20} color={colors.brandBlue} />
            <Body>{t(benefit)}</Body>
          </View>
        ))}
      </View>

      <Card style={styles.form}>
        <Text style={styles.label}>{t("sell.goal")}</Text>
        <Segmented
          options={[
            { value: "sell", label: t("sell.goalSell") },
            { value: "rent", label: t("sell.goalRent") },
          ]}
          value={form.kind}
          onChange={(kind) => set({ kind })}
        />
        <Field
          label={t("sell.name")}
          value={form.fullName}
          onChangeText={(fullName) => set({ fullName })}
          autoComplete="name"
          textContentType="name"
          error={errors.fullName}
        />
        <Field
          label={t("sell.phone")}
          value={form.phone}
          onChangeText={(phone) => set({ phone })}
          keyboardType="phone-pad"
          autoComplete="tel"
          textContentType="telephoneNumber"
          error={errors.phone}
        />
        <Field
          label={t("sell.municipality")}
          value={form.municipality}
          onChangeText={(municipality) => set({ municipality })}
          error={errors.municipality}
        />
        <Text style={styles.label}>{t("sell.type")}</Text>
        <View style={styles.wrap}>
          {TYPES.map((type) => (
            <Chip
              key={type}
              label={tEnum("propertyType", type)}
              selected={form.propertyType === type}
              onPress={() => set({ propertyType: type })}
            />
          ))}
        </View>
        <Text style={styles.label}>{t("sell.intention")}</Text>
        {INTENTIONS.map((intention) => {
          const selected = form.intention === intention;
          return (
            <Pressable
              key={intention}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              onPress={() => set({ intention })}
              style={[styles.option, selected && styles.optionSelected]}
            >
              <Ionicons
                name={selected ? "radio-button-on" : "radio-button-off"}
                size={20}
                color={colors.brandBlue}
              />
              <Text style={styles.optionText}>{t(`intention.${intention}`)}</Text>
            </Pressable>
          );
        })}
        {errors.intention ? <Text style={styles.error}>{errors.intention}</Text> : null}
        <Field
          label={t("sell.message")}
          value={form.message}
          onChangeText={(message) => set({ message })}
          multiline
          maxLength={2000}
        />
        <Checkbox
          checked={form.privacyAccepted}
          label={t("sell.privacy")}
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
          label={t("sell.marketing")}
          onToggle={() => set({ marketingAccepted: !form.marketingAccepted })}
        />
        {send.isError ? (
          <View style={styles.sendError}>
            <Text style={styles.error}>{t("sell.error")}</Text>
            <Button
              label={t("contact.call")}
              variant="secondary"
              icon="call"
              onPress={() => void contact.call()}
            />
          </View>
        ) : null}
        <Button
          label={send.isPending ? t("sell.sending") : t("sell.submit")}
          onPress={submit}
          busy={send.isPending}
        />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  intro: { gap: spacing.md },
  benefit: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  form: { gap: spacing.lg, padding: spacing.xl },
  field: { gap: spacing.xs },
  label: { fontSize: typography.sizes.sm, fontWeight: "600", color: colors.gray900 },
  input: {
    minHeight: 48,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.gray300,
    backgroundColor: colors.white,
    fontSize: typography.sizes.md,
    color: colors.gray900,
  },
  inputError: { borderColor: colors.danger },
  error: { fontSize: typography.sizes.xs, color: colors.danger },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.gray300,
  },
  optionSelected: { borderColor: colors.brandBlue, backgroundColor: colors.brandLightBlueSoft },
  optionText: { flex: 1, fontSize: typography.sizes.md, color: colors.gray900 },
  checkbox: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  checkboxLabel: { flex: 1, fontSize: typography.sizes.sm, color: colors.gray700, lineHeight: 20 },
  link: { color: colors.brandBlue, fontWeight: "600", marginLeft: 36 },
  sendError: { gap: spacing.sm },
  success: { flexGrow: 1, alignItems: "center", justifyContent: "center", gap: spacing.lg },
  center: { textAlign: "center" },
});
