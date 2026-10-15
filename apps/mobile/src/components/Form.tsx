import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, TextInput, View, type TextInputProps } from "react-native";

import { colors, radii, spacing, typography } from "../theme";

export function Field({
  label,
  error,
  hint,
  ...input
}: { label: string; error?: string | undefined; hint?: string } & TextInputProps) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.gray500}
        style={[styles.input, error ? styles.inputError : null]}
        {...input}
      />
      {error ? (
        <Text style={styles.error}>{error}</Text>
      ) : hint ? (
        <Text style={styles.hint}>{hint}</Text>
      ) : null}
    </View>
  );
}

export function Checkbox({
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

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <View style={styles.formError} accessibilityRole="alert">
      <Text style={styles.formErrorText}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
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
  hint: { fontSize: typography.sizes.xs, color: colors.gray500 },
  checkbox: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  checkboxLabel: { flex: 1, fontSize: typography.sizes.sm, color: colors.gray700, lineHeight: 20 },
  formError: {
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.dangerSoft,
  },
  formErrorText: { color: colors.danger, fontSize: typography.sizes.sm },
});
