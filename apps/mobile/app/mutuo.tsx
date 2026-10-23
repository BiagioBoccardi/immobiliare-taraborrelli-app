import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Field } from "../src/components/Form";
import { Screen } from "../src/components/Screen";
import { Body, Button, Card, Chip, Heading } from "../src/components/ui";
import { formatEuro } from "../src/format";
import { t } from "../src/i18n";
import {
  computeMortgage,
  DEFAULT_RATE,
  DEFAULT_YEARS,
  defaultDownPayment,
  MORTGAGE_YEARS,
  parseNumber,
  USUAL_MAX_LOAN_SHARE,
  validateMortgage,
} from "../src/mortgage";
import { colors, radii, spacing, typography } from "../src/theme";

/** Amount as typed in the field, without the currency: "120.000". */
function amountText(value: number): string {
  return formatEuro(value).replace(" €", "");
}

function ResultRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.resultRow}>
      <Body muted>{label}</Body>
      <Text style={styles.resultValue}>{value}</Text>
    </View>
  );
}

export default function Mortgage() {
  // Opened from a property, the price is already filled in.
  const { prezzo } = useLocalSearchParams<{ prezzo?: string }>();
  const initialPrice = prezzo ? parseNumber(prezzo) : null;
  const [price, setPrice] = useState(initialPrice ? amountText(initialPrice) : "");
  const [downPayment, setDownPayment] = useState(
    initialPrice ? amountText(defaultDownPayment(initialPrice)) : "",
  );
  const [years, setYears] = useState<number>(DEFAULT_YEARS);
  const [rate, setRate] = useState(String(DEFAULT_RATE).replace(".", ","));

  const input = {
    price: parseNumber(price) ?? 0,
    downPayment: parseNumber(downPayment) ?? 0,
    years,
    annualRate: parseNumber(rate) ?? -1,
  };
  const error = validateMortgage(input);
  const result = error === null ? computeMortgage(input) : null;
  const downPercent = input.price > 0 ? Math.round((input.downPayment / input.price) * 100) : null;

  return (
    <Screen width="narrow">
      <View style={styles.top}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
          onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))}
          hitSlop={8}
          style={styles.back}
        >
          <Ionicons name="chevron-back" size={22} color={colors.gray900} />
        </Pressable>
      </View>
      <View style={styles.header}>
        <Heading size="xxl">{t("mortgage.title")}</Heading>
        <Body muted>{t("mortgage.subtitle")}</Body>
      </View>

      <Card style={styles.form}>
        <Field
          label={t("mortgage.price")}
          value={price}
          onChangeText={setPrice}
          keyboardType="numeric"
          inputMode="numeric"
          placeholder="150.000"
          error={price && error === "invalidPrice" ? t("mortgage.invalidPrice") : undefined}
        />
        <Field
          label={t("mortgage.downPayment")}
          value={downPayment}
          onChangeText={setDownPayment}
          keyboardType="numeric"
          inputMode="numeric"
          placeholder="30.000"
          error={error === "invalidDownPayment" ? t("mortgage.invalidDownPayment") : undefined}
          {...(downPercent !== null && error !== "invalidDownPayment"
            ? { hint: t("mortgage.downPaymentHint", { percent: downPercent }) }
            : {})}
        />
        <View style={styles.years}>
          <Text style={styles.label}>{t("mortgage.years")}</Text>
          <View style={styles.chips}>
            {MORTGAGE_YEARS.map((value) => (
              <Chip
                key={value}
                label={t("mortgage.yearsValue", { years: value })}
                selected={years === value}
                onPress={() => setYears(value)}
              />
            ))}
          </View>
        </View>
        <Field
          label={t("mortgage.rate")}
          value={rate}
          onChangeText={setRate}
          keyboardType="decimal-pad"
          inputMode="decimal"
          error={error === "invalidRate" ? t("mortgage.invalidRate") : undefined}
          hint={t("mortgage.rateHint")}
        />
      </Card>

      {result ? (
        <Card style={styles.result}>
          <Body muted>{t("mortgage.monthly")}</Body>
          <Text style={styles.monthly} accessibilityLabel={t("mortgage.monthly")}>
            {formatEuro(result.monthlyPayment)}
          </Text>
          <ResultRow label={t("mortgage.loan")} value={formatEuro(result.loan)} />
          <ResultRow label={t("mortgage.interest")} value={formatEuro(result.totalInterest)} />
          <ResultRow label={t("mortgage.total")} value={formatEuro(result.totalPaid)} />
          <Body muted>{t("mortgage.ratio", { percent: Math.round(result.loanShare * 100) })}</Body>
          {result.loanShare > USUAL_MAX_LOAN_SHARE ? (
            <View style={styles.warning}>
              <Ionicons name="alert-circle-outline" size={18} color={colors.warning} />
              <Body style={styles.warningText}>{t("mortgage.highRatio")}</Body>
            </View>
          ) : null}
        </Card>
      ) : null}

      {/* Calculators always say that the result is indicative (CLAUDE.md, section 11). */}
      <View style={styles.disclaimer}>
        <Ionicons name="information-circle-outline" size={18} color={colors.gray500} />
        <Body muted style={styles.disclaimerText}>
          {t("mortgage.disclaimer")}
        </Body>
      </View>
      <Button
        label={t("mortgage.contact")}
        icon="call"
        variant="secondary"
        onPress={() => router.push("/contatti")}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row" },
  back: {
    width: 40,
    height: 40,
    borderRadius: radii.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
  },
  header: { gap: spacing.sm },
  form: { gap: spacing.lg },
  years: { gap: spacing.sm },
  label: { fontSize: typography.sizes.sm, fontWeight: "600", color: colors.gray900 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  result: { gap: spacing.sm },
  monthly: {
    fontSize: typography.sizes.display,
    fontWeight: "700",
    color: colors.brandBlue,
    marginBottom: spacing.sm,
  },
  resultRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  resultValue: { fontSize: typography.sizes.md, fontWeight: "600", color: colors.gray900 },
  warning: {
    flexDirection: "row",
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.warningSoft,
  },
  warningText: { flex: 1 },
  disclaimer: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  disclaimerText: { flex: 1 },
});
