import { Ionicons } from "@expo/vector-icons";
import type { ComponentProps, ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";

import { t } from "../i18n";
import { cardShadow, colors, fonts, radii, spacing, typography } from "../theme";

export type IconName = ComponentProps<typeof Ionicons>["name"];

export function Heading({
  children,
  size = "xl",
  style,
}: {
  children: ReactNode;
  size?: "lg" | "xl" | "xxl" | "display";
  style?: StyleProp<TextStyle>;
}) {
  return (
    <Text
      accessibilityRole="header"
      style={[styles.heading, { fontSize: typography.sizes[size] }, style]}
    >
      {children}
    </Text>
  );
}

export function Body({
  children,
  muted = false,
  style,
}: {
  children: ReactNode;
  muted?: boolean;
  style?: StyleProp<TextStyle>;
}) {
  return <Text style={[styles.body, muted && styles.muted, style]}>{children}</Text>;
}

export function Button({
  label,
  onPress,
  icon,
  variant = "primary",
  disabled = false,
  busy = false,
  style,
}: {
  label: string;
  onPress: () => void;
  icon?: IconName;
  variant?: "primary" | "secondary" | "light";
  disabled?: boolean;
  busy?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const textColor = variant === "primary" ? colors.white : colors.brandBlue;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || busy }}
      disabled={disabled || busy}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        variant === "primary" && styles.buttonPrimary,
        variant === "secondary" && styles.buttonSecondary,
        variant === "light" && styles.buttonLight,
        (disabled || busy) && styles.disabled,
        pressed && styles.pressed,
        style,
      ]}
    >
      {busy ? <ActivityIndicator color={textColor} /> : null}
      {!busy && icon ? <Ionicons name={icon} size={18} color={textColor} /> : null}
      <Text style={[styles.buttonText, { color: textColor }]}>{label}</Text>
    </Pressable>
  );
}

export function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.chip, selected && styles.chipSelected]}
    >
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  style,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[styles.segmented, style]} accessibilityRole="tablist">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            onPress={() => onChange(option.value)}
            style={[styles.segment, selected && styles.segmentSelected]}
          >
            <Text style={[styles.segmentText, selected && styles.segmentTextSelected]}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function SectionHeader({
  title,
  actionLabel,
  onAction,
}: {
  title: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <View style={styles.sectionHeader}>
      <Heading size="lg">{title}</Heading>
      {actionLabel && onAction ? (
        <Pressable accessibilityRole="link" onPress={onAction} hitSlop={8}>
          <Text style={styles.link}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon: IconName;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <View style={styles.empty}>
      <Ionicons name={icon} size={40} color={colors.brandLightBlue} />
      <Body style={styles.emptyTitle}>{title}</Body>
      {hint ? (
        <Body muted style={styles.center}>
          {hint}
        </Body>
      ) : null}
      {action}
    </View>
  );
}

export function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <EmptyState
      icon="cloud-offline-outline"
      title={t("common.error")}
      action={<Button label={t("common.retry")} variant="secondary" onPress={onRetry} />}
    />
  );
}

export function Loading() {
  return (
    <View style={styles.empty} accessibilityLabel={t("common.loading")}>
      <ActivityIndicator color={colors.brandBlue} />
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  heading: {
    fontFamily: fonts.heading,
    color: colors.gray900,
  },
  body: {
    fontSize: typography.sizes.sm,
    lineHeight: typography.sizes.sm * typography.lineHeight,
    color: colors.gray700,
  },
  muted: { color: colors.gray500 },
  center: { textAlign: "center" },
  button: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    minHeight: 48,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
  },
  buttonPrimary: { backgroundColor: colors.brandBlue },
  buttonSecondary: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.gray300,
  },
  buttonLight: { backgroundColor: colors.white },
  buttonText: { fontSize: typography.sizes.md, fontWeight: "600" },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.85 },
  chip: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.gray100,
  },
  chipSelected: { backgroundColor: colors.brandBlue, borderColor: colors.brandBlue },
  chipText: { fontSize: typography.sizes.sm, color: colors.gray700, fontWeight: "500" },
  chipTextSelected: { color: colors.white },
  segmented: {
    flexDirection: "row",
    padding: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.brandBlueDark,
  },
  segment: {
    flex: 1,
    alignItems: "center",
    paddingVertical: spacing.md,
    borderRadius: radii.pill,
  },
  segmentSelected: { backgroundColor: colors.white },
  segmentText: { fontSize: typography.sizes.md, color: colors.white, fontWeight: "600" },
  segmentTextSelected: { color: colors.brandBlue },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  link: { color: colors.brandBlue, fontWeight: "600", fontSize: typography.sizes.sm },
  empty: {
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    padding: spacing.xxl,
  },
  emptyTitle: {
    fontSize: typography.sizes.md,
    color: colors.gray900,
    fontWeight: "600",
    textAlign: "center",
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: radii.lg,
    padding: spacing.lg,
    ...cardShadow,
  },
});
