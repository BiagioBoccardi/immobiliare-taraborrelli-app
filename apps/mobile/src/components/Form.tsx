import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, TextInput, View, type TextInputProps } from "react-native";

import { colors, radii, spacing, typography } from "../theme";

export function Field({
  label,
  error,
  hint,
  onDark = false,
  ...input
}: {
  label: string;
  error?: string | undefined;
  hint?: string;
  /** On the brand blue background (login on desktop). */
  onDark?: boolean;
} & TextInputProps) {
  return (
    <View style={styles.field}>
      <Text style={[styles.label, onDark && styles.textOnDark]}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.gray500}
        style={[styles.input, onDark && styles.inputLarge, error ? styles.inputError : null]}
        {...input}
      />
      {error ? (
        <Text style={[styles.error, onDark && styles.errorOnDark]}>{error}</Text>
      ) : hint ? (
        <Text style={[styles.hint, onDark && styles.hintOnDark]}>{hint}</Text>
      ) : null}
    </View>
  );
}

export function Checkbox({
  checked,
  label,
  onToggle,
  error,
  onDark = false,
}: {
  checked: boolean;
  label: string;
  onToggle: () => void;
  error?: string | undefined;
  onDark?: boolean;
}) {
  const iconColor = onDark ? colors.white : error ? colors.danger : colors.brandBlue;
  return (
    <View>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked }}
        onPress={onToggle}
        style={styles.checkbox}
      >
        <Ionicons name={checked ? "checkbox" : "square-outline"} size={24} color={iconColor} />
        <Text style={[styles.checkboxLabel, onDark && styles.textOnDark]}>{label}</Text>
      </Pressable>
      {error ? <Text style={[styles.error, onDark && styles.errorOnDark]}>{error}</Text> : null}
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
  textOnDark: { color: colors.white, fontSize: typography.sizes.md },
  inputLarge: { minHeight: 56, fontSize: typography.sizes.lg },
  hintOnDark: { color: colors.brandLightBlueSoft },
  errorOnDark: { color: colors.dangerSoft, fontWeight: "600" },
  formError: {
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.dangerSoft,
  },
  formErrorText: { color: colors.danger, fontSize: typography.sizes.sm },
});
