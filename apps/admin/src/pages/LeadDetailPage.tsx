import type { Lead, LeadPriority, LeadStatus } from "@taraborrelli/api-client";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useDeleteLead, useLead, useUpdateLead } from "../api/queries";
import { LeadStatusBadge, PriorityBadge } from "../components/badges";
import {
  ConfirmDialog,
  ErrorAlert,
  Field,
  Loading,
  PageHeader,
  SuccessAlert,
} from "../components/ui";
import { hasTranslation, t, tEnum } from "../i18n";
import {
  formatDate,
  formatDateTime,
  formatEuro,
  fromLocalInput,
  internationalPhone,
  toLocalInput,
} from "../utils/format";

const STATUSES: LeadStatus[] = [
  "new",
  "contacted",
  "appointment_scheduled",
  "mandate_acquired",
  "lost",
];
const PRIORITIES: LeadPriority[] = ["high", "medium", "low"];

/** Human-readable value for a field of the optional second step of a valuation. */
function detailValue(key: string, value: unknown): string {
  if (typeof value === "boolean") return value ? t("common.yes") : t("common.no");
  if (key === "expected_price" && typeof value === "number") return formatEuro(value);
  if (key === "sell_timeline" && typeof value === "string") return tEnum("sellTimeline", value);
  if (key === "parts_condition" && value && typeof value === "object") {
    return Object.entries(value as Record<string, string>)
      .map(([part, condition]) => `${tEnum("part", part)}: ${tEnum("partCondition", condition)}`)
      .join(", ");
  }
  return String(value);
}

function detailLabel(key: string): string {
  const translationKey = `details.${key}`;
  return hasTranslation(translationKey) ? t(translationKey) : key;
}

function CrmForm({ lead }: { lead: Lead }) {
  const update = useUpdateLead(lead.id);
  const [status, setStatus] = useState<LeadStatus>(lead.status);
  const [priority, setPriority] = useState<LeadPriority>(lead.priority);
  const [nextContact, setNextContact] = useState(toLocalInput(lead.next_contact_at));
  const [notes, setNotes] = useState(lead.staff_notes ?? "");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({
      status,
      priority,
      next_contact_at: fromLocalInput(nextContact),
      staff_notes: notes.trim() || null,
    });
  };

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>{t("leads.crm")}</h2>
      {update.isSuccess ? <SuccessAlert>{t("common.saved")}</SuccessAlert> : null}
      <ErrorAlert error={update.error} />
      <Field label={t("leads.status")} htmlFor="crm-status">
        <select
          id="crm-status"
          value={status}
          onChange={(e) => setStatus(e.target.value as LeadStatus)}
        >
          {STATUSES.map((value) => (
            <option key={value} value={value}>
              {tEnum("leadStatus", value)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("leads.priority")} htmlFor="crm-priority">
        <select
          id="crm-priority"
          value={priority}
          onChange={(e) => setPriority(e.target.value as LeadPriority)}
        >
          {PRIORITIES.map((value) => (
            <option key={value} value={value}>
              {tEnum("leadPriority", value)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("leads.nextContact")} htmlFor="crm-next">
        <input
          id="crm-next"
          type="datetime-local"
          value={nextContact}
          onChange={(e) => setNextContact(e.target.value)}
        />
      </Field>
      <Field label={t("leads.staffNotes")} htmlFor="crm-notes">
        <textarea
          id="crm-notes"
          maxLength={2000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </Field>
      <button type="submit" className="button button-primary" disabled={update.isPending}>
        {update.isPending ? t("common.saving") : t("common.save")}
      </button>
    </form>
  );
}

export function LeadDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const lead = useLead(id);
  const remove = useDeleteLead();
  const [confirming, setConfirming] = useState(false);

  if (lead.isPending) return <Loading />;
  if (lead.error || !lead.data) return <ErrorAlert error={lead.error} />;
  const data = lead.data;
  const phone = internationalPhone(data.phone);
  const details = Object.entries(data.details ?? {}).filter(
    ([, value]) => value !== null && value !== "" && value !== false,
  );

  return (
    <>
      <PageHeader
        title={data.full_name}
        subtitle={
          <span className="row">
            {tEnum("leadKind", data.kind)} · {formatDateTime(data.created_at)}
            <PriorityBadge priority={data.priority} />
            <LeadStatusBadge status={data.status} />
          </span>
        }
        actions={
          <>
            <Link to="/leads" className="button button-secondary">
              {t("common.back")}
            </Link>
            <button
              type="button"
              className="button button-danger"
              onClick={() => setConfirming(true)}
            >
              {t("common.delete")}
            </button>
          </>
        }
      />
      <div className="detail-layout">
        <div className="stack">
          <section className="card">
            <h2>{t("leads.contact")}</h2>
            <dl className="facts">
              <dt>{t("details.email")}</dt>
              <dd>{data.email ?? t("common.none")}</dd>
              <dt>{t("leads.phone")}</dt>
              <dd>{data.phone}</dd>
            </dl>
            <div className="row section-gap">
              <a className="button button-primary" href={`tel:${phone}`}>
                {t("leads.call")}
              </a>
              <a
                className="button button-secondary"
                href={`https://wa.me/${phone.replace("+", "")}`}
                target="_blank"
                rel="noreferrer"
              >
                {t("leads.whatsapp")}
              </a>
              {data.email ? (
                <a className="button button-secondary" href={`mailto:${data.email}`}>
                  {t("leads.email")}
                </a>
              ) : null}
            </div>
          </section>

          <section className="card">
            <h2>{t("leads.property")}</h2>
            <dl className="facts">
              <dt>{t("leads.intention")}</dt>
              <dd>{tEnum("intention", data.intention)}</dd>
              <dt>{t("leads.municipality")}</dt>
              <dd>{data.municipality}</dd>
              <dt>{t("properties.type")}</dt>
              <dd>{tEnum("propertyType", data.property_type)}</dd>
              <dt>{t("details.surface")}</dt>
              <dd>{data.surface_sqm ? `${data.surface_sqm} m²` : t("common.none")}</dd>
              <dt>{t("details.rooms")}</dt>
              <dd>{data.rooms ?? t("common.none")}</dd>
              <dt>{t("details.condition")}</dt>
              <dd>{tEnum("condition", data.condition)}</dd>
            </dl>
          </section>

          <section className="card">
            <h2>{t("leads.details")}</h2>
            {details.length === 0 ? (
              <p className="muted">{t("leads.noDetails")}</p>
            ) : (
              <dl className="facts">
                {details.map(([key, value]) => (
                  <div key={key} className="contents">
                    <dt>{detailLabel(key)}</dt>
                    <dd>{detailValue(key, value)}</dd>
                  </div>
                ))}
              </dl>
            )}
            {data.message ? (
              <>
                <h3 className="section-gap">{t("leads.message")}</h3>
                <p>{data.message}</p>
              </>
            ) : null}
          </section>

          <section className="card">
            <h2>{t("leads.consent")}</h2>
            <p>
              {t("leads.consentContact", {
                date: formatDate(data.contact_consent_at),
                version: data.privacy_policy_version,
              })}
            </p>
            <p>
              {t("leads.consentMarketing")}:{" "}
              {data.marketing_consent ? t("common.yes") : t("common.no")}
            </p>
          </section>
        </div>
        <CrmForm lead={data} />
      </div>

      {confirming ? (
        <ConfirmDialog
          title={t("leads.deleteTitle")}
          body={t("leads.deleteBody")}
          confirmLabel={t("common.delete")}
          busy={remove.isPending}
          onCancel={() => setConfirming(false)}
          onConfirm={() =>
            remove.mutate(data.id, { onSuccess: () => navigate("/leads", { replace: true }) })
          }
        />
      ) : null}
    </>
  );
}
