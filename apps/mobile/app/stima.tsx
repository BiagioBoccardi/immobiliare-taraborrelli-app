import { Ionicons } from "@expo/vector-icons";
import type { Estimate, Place, ValuationCreated } from "@taraborrelli/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState, type ReactNode } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { api } from "../src/api";
import { AddressMap } from "../src/components/AddressMap";
import { Checkbox, Field } from "../src/components/Form";
import { Body, Button, Card, Chip, Heading, type IconName } from "../src/components/ui";
import { privacy } from "../src/config";
import { contact } from "../src/contact";
import { formatEuro, formatNumber } from "../src/format";
import { t, tEnum, type TranslationKey } from "../src/i18n";
import { useLayout, NARROW_MAX_WIDTH } from "../src/layout";
import { useSession } from "../src/session";
import { colors, radii, spacing, typography } from "../src/theme";
import {
  CADASTRAL_CATEGORIES,
  CONDITIONS,
  EMPTY_VALUATION,
  FLOORS,
  HOME_TYPES,
  INTENTIONS,
  WORKS,
  isAnswered,
  isFlat,
  stepErrors,
  stepsFor,
  toValuationRequest,
  type HomeType,
  type Step,
  type StepErrors,
  type ValuationForm,
} from "../src/valuation";

const TYPE_ICONS: Record<HomeType, IconName> = {
  apartment: "business-outline",
  house: "home-outline",
  villa: "leaf-outline",
  attic: "sunny-outline",
};
const PROFESSIONAL: TranslationKey[] = [
  "estimate.professional1",
  "estimate.professional2",
  "estimate.professional3",
];

/** Full-width single choice, one per row (reference 03-domande-intenzione-tempi). */
function Options<T extends string | number>({
  options,
  value,
  onChange,
  label,
  icon,
}: {
  options: readonly T[];
  value: T | null;
  onChange: (value: T) => void;
  label: (value: T) => string;
  icon?: (value: T) => IconName;
}) {
  return (
    <View style={styles.options} accessibilityRole="radiogroup">
      {options.map((option) => {
        const selected = option === value;
        return (
          <Pressable
            key={String(option)}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            onPress={() => onChange(option)}
            style={[styles.option, selected && styles.optionSelected]}
          >
            {icon ? <Ionicons name={icon(option)} size={28} color={colors.brandBlue} /> : null}
            <Text style={[styles.optionText, selected && styles.optionTextSelected]}>
              {label(option)}
            </Text>
            <Ionicons
              name={selected ? "radio-button-on" : "radio-button-off"}
              size={22}
              color={colors.brandBlue}
            />
          </Pressable>
        );
      })}
    </View>
  );
}

function Question({
  title,
  body,
  children,
}: {
  title: string;
  body?: string;
  children: ReactNode;
}) {
  return (
    <View style={styles.question}>
      <Heading size="xxl">{title}</Heading>
      {body ? <Body muted>{body}</Body> : null}
      {children}
    </View>
  );
}

function AddressStep({
  form,
  set,
}: {
  form: ValuationForm;
  set: (changes: Partial<ValuationForm>) => void;
}) {
  const [query, setQuery] = useState(form.place?.label ?? "");
  const search = useMutation({ mutationFn: (text: string) => api.lead.geocode(text) });
  const choose = (place: Place) =>
    set({ place, latitude: place.latitude, longitude: place.longitude });
  // The search runs only on "Cerca": Nominatim does not allow search-as-you-type.
  const runSearch = () => {
    if (query.trim().length >= 3) search.mutate(query.trim());
  };

  if (form.place && form.latitude !== null && form.longitude !== null) {
    return (
      <Question title={t("estimate.addressTitle")}>
        <Card style={styles.chosen}>
          <Ionicons name="location" size={22} color={colors.brandBlue} />
          <Text style={styles.chosenText}>{form.place.label}</Text>
        </Card>
        <AddressMap
          latitude={form.latitude}
          longitude={form.longitude}
          onMove={(latitude, longitude) => set({ latitude, longitude })}
        />
        <Button
          label={t("estimate.changeAddress")}
          variant="secondary"
          onPress={() => set({ place: null, latitude: null, longitude: null })}
        />
      </Question>
    );
  }

  const places = search.data?.items ?? [];
  return (
    <Question title={t("estimate.addressTitle")} body={t("estimate.addressBody")}>
      <Field
        label={t("estimate.addressLabel")}
        placeholder={t("estimate.addressPlaceholder")}
        value={query}
        onChangeText={setQuery}
        autoComplete="street-address"
        textContentType="fullStreetAddress"
        returnKeyType="search"
        onSubmitEditing={runSearch}
      />
      <Button
        label={search.isPending ? t("estimate.searching") : t("estimate.search")}
        icon="search"
        variant="secondary"
        busy={search.isPending}
        disabled={query.trim().length < 3}
        onPress={runSearch}
      />
      {search.isError ? <Text style={styles.error}>{t("estimate.searchError")}</Text> : null}
      {search.isSuccess && places.length === 0 ? (
        <Body muted>{t("estimate.noResults")}</Body>
      ) : null}
      {places.length > 0 ? (
        <View style={styles.options}>
          <Text style={styles.label}>{t("estimate.chooseAddress")}</Text>
          {places.map((place) => (
            <Pressable
              key={`${place.latitude},${place.longitude}`}
              accessibilityRole="button"
              onPress={() => choose(place)}
              style={styles.option}
            >
              <Ionicons name="location-outline" size={22} color={colors.brandBlue} />
              <Text style={styles.optionText}>{place.label}</Text>
            </Pressable>
          ))}
          <Text style={styles.small}>{t("estimate.attribution")}</Text>
        </View>
      ) : null}
    </Question>
  );
}

function StepContent({
  step,
  form,
  set,
  errors,
}: {
  step: Step;
  form: ValuationForm;
  set: (changes: Partial<ValuationForm>) => void;
  errors: StepErrors;
}) {
  switch (step) {
    case "address":
      return <AddressStep form={form} set={set} />;
    case "type":
      return (
        <Question title={t("estimate.typeTitle")} body={t("estimate.typeBody")}>
          <Options
            options={HOME_TYPES}
            value={form.homeType}
            onChange={(homeType) => set({ homeType })}
            label={(type) => tEnum("homeType", type)}
            icon={(type) => TYPE_ICONS[type]}
          />
        </Question>
      );
    case "category":
      return (
        <Question title={t("estimate.categoryTitle")} body={t("estimate.categoryBody")}>
          <Options
            options={CADASTRAL_CATEGORIES}
            value={form.category}
            onChange={(category) => set({ category })}
            label={(category) => tEnum("cadastral", category)}
          />
        </Question>
      );
    case "size":
      return (
        <Question title={t("estimate.sizeTitle")} body={t("estimate.sizeBody")}>
          <Field
            label={t("estimate.surface")}
            hint={t("estimate.surfaceHint")}
            value={form.surface}
            onChangeText={(surface) => set({ surface })}
            keyboardType="number-pad"
            maxLength={5}
            error={errors.surface}
          />
          <Field
            label={t("estimate.rooms")}
            hint={t("estimate.roomsHint")}
            value={form.rooms}
            onChangeText={(rooms) => set({ rooms })}
            keyboardType="number-pad"
            maxLength={2}
            error={errors.rooms}
          />
        </Question>
      );
    case "floor":
      return (
        <Question title={t("estimate.floorTitle")} body={t("estimate.floorBody")}>
          <Text style={styles.label}>{t("estimate.floorLabel")}</Text>
          <View style={styles.chips}>
            {FLOORS.map((floor) => (
              <Chip
                key={floor}
                label={tEnum("floor", String(floor))}
                selected={form.floor === floor}
                onPress={() => set({ floor })}
              />
            ))}
          </View>
          <Text style={styles.label}>{t("estimate.elevatorLabel")}</Text>
          <Options
            options={["yes", "no"] as const}
            value={form.hasElevator === null ? null : form.hasElevator ? "yes" : "no"}
            onChange={(answer) => set({ hasElevator: answer === "yes" })}
            label={(answer) => t(answer === "yes" ? "common.yes" : "common.no")}
          />
        </Question>
      );
    case "condition":
      return (
        <Question title={t("estimate.conditionTitle")} body={t("estimate.conditionBody")}>
          <Options
            options={CONDITIONS}
            value={form.condition}
            onChange={(condition) => set({ condition })}
            label={(condition) => tEnum("leadCondition", condition)}
          />
        </Question>
      );
    case "works": {
      const flat = isFlat(form.homeType);
      return (
        <Question
          title={t(flat ? "estimate.worksTitleFlat" : "estimate.worksTitleHouse")}
          body={t(flat ? "estimate.worksBodyFlat" : "estimate.worksBodyHouse")}
        >
          <Options
            options={WORKS}
            value={form.works}
            onChange={(works) => set({ works })}
            label={(works) => tEnum("works", works)}
          />
        </Question>
      );
    }
    case "intention":
      return (
        <Question title={t("estimate.intentionTitle")} body={t("estimate.intentionBody")}>
          <Options
            options={INTENTIONS}
            value={form.intention}
            onChange={(intention) => set({ intention })}
            label={(intention) => t(`intention.${intention}`)}
          />
        </Question>
      );
    case "contacts":
      return (
        <Question title={t("estimate.contactsTitle")} body={t("estimate.contactsBody")}>
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
          <Checkbox
            checked={form.privacyAccepted}
            label={t("sell.privacy")}
            onToggle={() => set({ privacyAccepted: !form.privacyAccepted })}
            error={errors.privacy}
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
        </Question>
      );
  }
}

/** Range on a bar with minimum and maximum (reference 05-stima-a-intervallo). */
function EstimateRange({ estimate }: { estimate: Estimate }) {
  const omi = estimate.basis !== "agency_listings";
  const zone = estimate.zone_description
    ? `${estimate.zone_code} (${estimate.zone_description.toLowerCase()})`
    : (estimate.zone_code ?? "");
  const inMunicipality =
    estimate.listings_scope === "municipality" || estimate.listings_scope === "municipality_type";
  const basis = omi
    ? t("estimate.resultZone", { zone, municipality: estimate.municipality })
    : t(inMunicipality ? "estimate.resultListingsPlace" : "estimate.resultListingsAgency", {
        count: estimate.listings ?? 0,
        municipality: estimate.municipality,
      });
  return (
    <Card style={styles.result}>
      <Text style={styles.resultLabel}>{t("estimate.resultTitle")}</Text>
      <Text style={styles.resultRange}>
        {t("estimate.resultRange", {
          min: formatEuro(estimate.min_value),
          max: formatEuro(estimate.max_value),
        })}
      </Text>
      <View style={styles.bar} accessibilityElementsHidden importantForAccessibility="no">
        <View style={styles.barDot} />
        <View style={styles.barFill} />
        <View style={styles.barDot} />
      </View>
      <View style={styles.barLabels}>
        <View>
          <Text style={styles.small}>{t("estimate.minLabel")}</Text>
          <Text style={styles.barValue}>{formatEuro(estimate.min_value)}</Text>
        </View>
        <View style={styles.alignEnd}>
          <Text style={styles.small}>{t("estimate.maxLabel")}</Text>
          <Text style={styles.barValue}>{formatEuro(estimate.max_value)}</Text>
        </View>
      </View>
      <Body>
        {t("estimate.resultPerSqm", {
          min: formatNumber(estimate.min_per_sqm),
          max: formatNumber(estimate.max_per_sqm),
        })}{" "}
        · {basis}
      </Body>
      <View style={styles.notice}>
        <Ionicons name="information-circle-outline" size={20} color={colors.brandBlue} />
        <Text style={styles.noticeText}>
          {omi
            ? t("estimate.disclaimer", { semester: estimate.semester ?? "" })
            : t("estimate.disclaimerListings")}
        </Text>
      </View>
    </Card>
  );
}

function Result({ created }: { created: ValuationCreated }) {
  const reason = created.estimate_unavailable;
  return (
    <View style={styles.question}>
      {created.estimate ? (
        <EstimateRange estimate={created.estimate} />
      ) : (
        <Card style={styles.result}>
          <Ionicons name="checkmark-circle" size={48} color={colors.success} />
          <Heading size="xl">{t("estimate.unavailableTitle")}</Heading>
          {reason ? <Body>{t(`estimate.unavailable.${reason}`)}</Body> : null}
        </Card>
      )}
      <Card style={styles.result}>
        <Heading size="lg">{t("estimate.professionalTitle")}</Heading>
        {PROFESSIONAL.map((item) => (
          <View key={item} style={styles.benefit}>
            <Ionicons name="checkmark-circle" size={20} color={colors.brandBlue} />
            <Body style={styles.flex}>{t(item)}</Body>
          </View>
        ))}
        <Body muted>{t("estimate.received")}</Body>
        <Button label={t("estimate.call")} icon="call" onPress={() => void contact.call()} />
        <Button
          label={t("estimate.whatsapp")}
          icon="logo-whatsapp"
          variant="secondary"
          onPress={() => void contact.whatsapp(t("estimate.whatsappMessage"))}
        />
      </Card>
    </View>
  );
}

export default function EstimateWizard() {
  const { user } = useSession();
  const queryClient = useQueryClient();
  const { isDesktop } = useLayout();
  const [form, setForm] = useState<ValuationForm>({
    ...EMPTY_VALUATION,
    fullName: user?.full_name ?? "",
  });
  const [index, setIndex] = useState(0);
  const [errors, setErrors] = useState<StepErrors>({});
  const send = useMutation({
    mutationFn: () => api.lead.createValuation(toValuationRequest(form)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me", "requests"] }),
  });
  const set = (changes: Partial<ValuationForm>) =>
    setForm((current) => ({ ...current, ...changes }));

  const steps = stepsFor(form);
  const step = steps[Math.min(index, steps.length - 1)] ?? "address";
  const last = index >= steps.length - 1;
  const close = () => (router.canGoBack() ? router.back() : router.replace("/vendi"));

  const next = () => {
    const found = stepErrors(step, form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    if (last) send.mutate();
    else setIndex(index + 1);
  };
  const back = () => {
    setErrors({});
    if (index === 0) close();
    else setIndex(index - 1);
  };

  const width = isDesktop ? { maxWidth: NARROW_MAX_WIDTH, width: "100%" as const } : null;

  if (send.data) {
    return (
      <SafeAreaView style={styles.safe}>
        <ScrollView contentContainerStyle={[styles.body, width, styles.centered]}>
          <Result created={send.data} />
          <Button label={t("estimate.done")} variant="secondary" onPress={close} />
        </ScrollView>
      </SafeAreaView>
    );
  }

  const progress = (index + 1) / steps.length;
  return (
    <SafeAreaView style={styles.safe}>
      <View style={[styles.header, width, styles.centered]}>
        <View style={styles.headerRow}>
          <Text style={styles.stepText}>
            {t("estimate.step", { current: index + 1, total: steps.length })}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("estimate.close")}
            onPress={close}
            hitSlop={8}
          >
            <Ionicons name="close" size={26} color={colors.gray700} />
          </Pressable>
        </View>
        <View
          style={styles.progress}
          accessibilityRole="progressbar"
          accessibilityValue={{ min: 0, max: steps.length, now: index + 1 }}
        >
          <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
        </View>
      </View>
      <ScrollView
        contentContainerStyle={[styles.body, width, styles.centered]}
        keyboardShouldPersistTaps="handled"
      >
        <StepContent step={step} form={form} set={set} errors={errors} />
        {send.isError ? (
          <View style={styles.sendError}>
            <Text style={styles.error}>{t("estimate.sendError")}</Text>
            <Button
              label={t("contact.call")}
              variant="secondary"
              icon="call"
              onPress={() => void contact.call()}
            />
          </View>
        ) : null}
      </ScrollView>
      <View style={[styles.footer, width, styles.centered]}>
        <Button
          label={t("estimate.back")}
          variant="secondary"
          onPress={back}
          style={styles.backButton}
        />
        <Button
          label={
            last
              ? send.isPending
                ? t("estimate.sending")
                : t("estimate.submit")
              : t("estimate.next")
          }
          onPress={next}
          busy={send.isPending}
          disabled={!isAnswered(step, form)}
          style={styles.flex}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.white },
  centered: { alignSelf: "center" },
  header: { width: "100%", paddingHorizontal: spacing.xl, paddingTop: spacing.md, gap: spacing.sm },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  stepText: { fontSize: typography.sizes.sm, color: colors.gray700 },
  progress: {
    height: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.gray100,
    overflow: "hidden",
  },
  progressFill: { height: "100%", backgroundColor: colors.brandBlue },
  body: { width: "100%", padding: spacing.xl, paddingBottom: spacing.xxxl, gap: spacing.xl },
  question: { gap: spacing.lg },
  options: { gap: spacing.sm },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    minHeight: 56,
    padding: spacing.lg,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.gray300,
    backgroundColor: colors.white,
  },
  optionSelected: { borderColor: colors.brandBlue, backgroundColor: colors.brandLightBlueSoft },
  optionText: { flex: 1, fontSize: typography.sizes.md, color: colors.gray900 },
  optionTextSelected: { fontWeight: "600", color: colors.brandBlueDark },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  label: { fontSize: typography.sizes.sm, fontWeight: "600", color: colors.gray900 },
  small: { fontSize: typography.sizes.xs, color: colors.gray500 },
  error: { fontSize: typography.sizes.sm, color: colors.danger },
  link: { color: colors.brandBlue, fontWeight: "600", marginLeft: 36 },
  chosen: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg },
  chosenText: { flex: 1, fontSize: typography.sizes.md, fontWeight: "600", color: colors.gray900 },
  footer: {
    width: "100%",
    flexDirection: "row",
    gap: spacing.md,
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
    backgroundColor: colors.white,
  },
  backButton: { minWidth: 110 },
  flex: { flex: 1 },
  sendError: { gap: spacing.sm },
  result: { gap: spacing.md, padding: spacing.xl },
  resultLabel: { fontSize: typography.sizes.sm, fontWeight: "600", color: colors.gray700 },
  resultRange: {
    fontSize: typography.sizes.xxl,
    fontWeight: "700",
    color: colors.brandBlue,
  },
  bar: { flexDirection: "row", alignItems: "center", marginTop: spacing.sm },
  barFill: { flex: 1, height: 6, backgroundColor: colors.brandLightBlue },
  barDot: {
    width: 16,
    height: 16,
    borderRadius: radii.pill,
    borderWidth: 3,
    borderColor: colors.brandBlue,
    backgroundColor: colors.white,
  },
  barLabels: { flexDirection: "row", justifyContent: "space-between" },
  barValue: { fontSize: typography.sizes.md, fontWeight: "600", color: colors.gray900 },
  alignEnd: { alignItems: "flex-end" },
  notice: {
    flexDirection: "row",
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radii.md,
    backgroundColor: colors.brandLightBlueSoft,
  },
  noticeText: { flex: 1, fontSize: typography.sizes.sm, color: colors.gray700, lineHeight: 20 },
  benefit: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
});
