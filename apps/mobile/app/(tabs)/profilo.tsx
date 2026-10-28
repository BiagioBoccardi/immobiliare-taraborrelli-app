import { Ionicons } from "@expo/vector-icons";
import { ApiError, type ConsentPurpose, type MyRequest } from "@taraborrelli/api-client";
import Constants from "expo-constants";
import { router } from "expo-router";
import { useState } from "react";
import { Linking, Pressable, Share, StyleSheet, Switch, Text, View } from "react-native";

import { api } from "../../src/api";
import { FormError } from "../../src/components/Form";
import { Screen } from "../../src/components/Screen";
import { Body, Button, Card, Heading, Loading, type IconName } from "../../src/components/ui";
import { privacy } from "../../src/config";
import { formatDate } from "../../src/format";
import { t, tError, type TranslationKey } from "../../src/i18n";
import { useChangeConsent, useMyConsents, useMyRequests } from "../../src/queries";
import { useSession, useSessionStore } from "../../src/session";
import { colors, radii, spacing, typography } from "../../src/theme";

const KIND_LABEL: Record<MyRequest["kind"], TranslationKey> = {
  valuation: "profile.requestValuation",
  sell: "profile.requestSell",
  rent: "profile.requestRent",
};

const CONSENTS: { purpose: ConsentPurpose; label: TranslationKey }[] = [
  { purpose: "marketing", label: "profile.consentMarketing" },
  { purpose: "push_notifications", label: "profile.consentPush" },
];

function Row({
  icon,
  label,
  onPress,
  danger = false,
}: {
  icon: IconName;
  label: string;
  onPress: () => void;
  danger?: boolean;
}) {
  const color = danger ? colors.danger : colors.brandBlue;
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.row}>
      <Ionicons name={icon} size={22} color={color} />
      <Text style={[styles.rowText, danger && styles.danger]}>{label}</Text>
      <Ionicons name="chevron-forward" size={20} color={colors.gray300} />
    </Pressable>
  );
}

const STATUS_LABEL: Record<MyRequest["status"], TranslationKey> = {
  new: "requestStatus.new",
  contacted: "requestStatus.contacted",
  appointment_scheduled: "requestStatus.appointment_scheduled",
  mandate_acquired: "requestStatus.mandate_acquired",
  lost: "requestStatus.lost",
};

function Requests() {
  const requests = useMyRequests();
  if (requests.isPending) return <Loading />;
  if (requests.isError) return <Body muted>{t("common.error")}</Body>;
  if (requests.data.items.length === 0) return <Body muted>{t("profile.requestsEmpty")}</Body>;
  return (
    <View style={styles.requests}>
      {requests.data.items.map((request) => (
        <View key={request.id} style={styles.request}>
          <View style={styles.requestText}>
            <Text style={styles.requestTitle}>
              {t(KIND_LABEL[request.kind])} · {request.municipality}
            </Text>
            <Body muted>{t("profile.sentOn", { date: formatDate(request.created_at) })}</Body>
          </View>
          <Text style={styles.badge}>{t(STATUS_LABEL[request.status])}</Text>
        </View>
      ))}
    </View>
  );
}

function Consents() {
  const consents = useMyConsents();
  const change = useChangeConsent();
  const granted = (purpose: ConsentPurpose) =>
    consents.data?.find((consent) => consent.purpose === purpose)?.granted ?? false;

  return (
    <>
      {CONSENTS.map(({ purpose, label }) => (
        <View key={purpose} style={styles.row}>
          <Text style={styles.rowText}>{t(label)}</Text>
          <Switch
            accessibilityLabel={t(label)}
            value={granted(purpose)}
            disabled={consents.isPending || change.isPending}
            onValueChange={(value) => change.mutate({ purpose, granted: value })}
            trackColor={{ true: colors.brandBlue, false: colors.gray300 }}
            thumbColor={colors.white}
          />
        </View>
      ))}
      {change.isError ? <FormError message={t("common.error")} /> : null}
    </>
  );
}

export default function Profile() {
  const session = useSessionStore();
  const { user } = useSession();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportData = async () => {
    setError(null);
    try {
      const data = await api.auth.exportMe();
      await Share.share({ message: JSON.stringify(data, null, 2) });
    } catch {
      setError(t("common.error"));
    }
  };

  const deleteAccount = async () => {
    setBusy(true);
    setError(null);
    try {
      await session.deleteAccount();
    } catch (caught) {
      setError(tError(caught instanceof ApiError ? caught.code : undefined));
      setBusy(false);
    }
  };

  return (
    <Screen width="narrow">
      <Heading size="xxl">{t("profile.title")}</Heading>

      <Card style={styles.user}>
        <Ionicons name="person-circle-outline" size={48} color={colors.brandLightBlue} />
        <View style={styles.requestText}>
          <Heading size="lg">{user?.full_name ?? ""}</Heading>
          <Body muted>{user?.email ?? ""}</Body>
        </View>
      </Card>

      <Heading size="lg">{t("profile.requests")}</Heading>
      <Card>
        <Requests />
      </Card>

      <Heading size="lg">{t("profile.consents")}</Heading>
      <Card style={styles.list}>
        <Consents />
      </Card>

      <FormError message={error} />
      <Card style={styles.list}>
        <Row
          icon="call-outline"
          label={t("profile.contact")}
          onPress={() => router.push("/contatti")}
        />
        <Row
          icon="calculator-outline"
          label={t("mortgage.title")}
          onPress={() => router.push("/mutuo")}
        />
        {privacy.url ? (
          <Row
            icon="shield-checkmark-outline"
            label={t("profile.privacy")}
            onPress={() => void Linking.openURL(privacy.url)}
          />
        ) : null}
        <Row
          icon="download-outline"
          label={t("profile.export")}
          onPress={() => void exportData()}
        />
        <Row
          icon="log-out-outline"
          label={t("profile.logout")}
          onPress={() => void session.logout()}
        />
        <Row
          icon="trash-outline"
          label={t("profile.delete")}
          danger
          onPress={() => setConfirmDelete(true)}
        />
      </Card>

      {confirmDelete ? (
        <Card style={styles.confirm}>
          <Body>{t("profile.deleteConfirm")}</Body>
          <Button label={t("profile.deleteYes")} onPress={() => void deleteAccount()} busy={busy} />
          <Button
            label={t("profile.deleteNo")}
            variant="secondary"
            onPress={() => setConfirmDelete(false)}
            disabled={busy}
          />
        </Card>
      ) : null}

      <View style={styles.version}>
        <Body muted>{t("profile.version", { version: Constants.expoConfig?.version ?? "" })}</Body>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  user: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  list: { paddingVertical: spacing.xs },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.md },
  rowText: { flex: 1, fontSize: typography.sizes.md, color: colors.gray900 },
  danger: { color: colors.danger },
  requests: { gap: spacing.md },
  request: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  requestText: { flex: 1, gap: spacing.xxs },
  requestTitle: { fontSize: typography.sizes.md, fontWeight: "600", color: colors.gray900 },
  badge: {
    fontSize: typography.sizes.sm,
    color: colors.brandBlueDark,
    backgroundColor: colors.brandLightBlueSoft,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xxs,
    overflow: "hidden",
  },
  confirm: { gap: spacing.md, borderColor: colors.danger, borderWidth: 1 },
  version: { alignItems: "center" },
});
