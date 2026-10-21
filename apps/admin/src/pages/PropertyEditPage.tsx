import type { AdminProperty } from "@taraborrelli/api-client";
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import {
  useChangeStatus,
  useCreateProperty,
  useDeleteProperty,
  useProperty,
  useUpdateProperty,
} from "../api/queries";
import { PropertyStatusBadge } from "../components/badges";
import { PhotoManager } from "../components/PhotoManager";
import { PropertyForm } from "../components/PropertyForm";
import { ConfirmDialog, ErrorAlert, Loading, PageHeader, SuccessAlert } from "../components/ui";
import { t, tEnum } from "../i18n";
import { formatDate } from "../utils/format";
import { EMPTY_FORM, STATUS_TRANSITIONS, formFromProperty, payloadFromForm } from "./propertyForm";

export function NewPropertyPage() {
  const create = useCreateProperty();
  const navigate = useNavigate();

  return (
    <>
      <PageHeader
        title={t("properties.new")}
        actions={
          <Link to="/properties" className="button button-secondary">
            {t("common.back")}
          </Link>
        }
      />
      <ErrorAlert error={create.error} />
      <PropertyForm
        initial={EMPTY_FORM}
        submitting={create.isPending}
        onSubmit={(form) =>
          create.mutate(payloadFromForm(form), {
            onSuccess: (property) =>
              navigate(`/properties/${property.id}`, { replace: true, state: { created: true } }),
          })
        }
      />
    </>
  );
}

function StatusPanel({ property }: { property: AdminProperty }) {
  const change = useChangeStatus(property.id);
  return (
    <section className="card stack">
      <h2>{t("properties.sectionStatus")}</h2>
      <div className="row">
        <span className="muted">{t("properties.currentStatus")}</span>
        <PropertyStatusBadge status={property.status} />
      </div>
      {property.published_at ? (
        <span className="hint">
          {t("properties.publishedAt", { date: formatDate(property.published_at) })}
        </span>
      ) : null}
      <ErrorAlert error={change.error} />
      <div className="row">
        <span className="muted">{t("properties.changeTo")}</span>
        {STATUS_TRANSITIONS[property.status].map((status) => (
          <button
            key={status}
            type="button"
            className={status === "published" ? "button button-primary" : "button button-secondary"}
            disabled={change.isPending}
            onClick={() => change.mutate(status)}
          >
            {tEnum("propertyStatus", status)}
          </button>
        ))}
      </div>
    </section>
  );
}

export function PropertyEditPage() {
  const { id = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const property = useProperty(id);
  const update = useUpdateProperty(id);
  const remove = useDeleteProperty();
  const [confirming, setConfirming] = useState(false);
  const created = (location.state as { created?: boolean } | null)?.created === true;

  if (property.isPending) return <Loading />;
  if (property.error || !property.data) return <ErrorAlert error={property.error} />;
  const data = property.data;

  return (
    <>
      <PageHeader
        title={data.title}
        subtitle={`${t("properties.reference")} ${data.reference} · ${tEnum("contract", data.contract)} · ${data.municipality}`}
        actions={
          <>
            <Link to="/properties" className="button button-secondary">
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
      <div className="stack">
        {created ? <SuccessAlert>{t("properties.created")}</SuccessAlert> : null}
        <StatusPanel property={data} />
        <PhotoManager property={data} />
        {update.isSuccess ? <SuccessAlert>{t("common.saved")}</SuccessAlert> : null}
        <ErrorAlert error={update.error} />
        <PropertyForm
          initial={formFromProperty(data)}
          submitting={update.isPending}
          onSubmit={(form) => update.mutate(payloadFromForm(form))}
        />
      </div>

      {confirming ? (
        <ConfirmDialog
          title={t("properties.deleteTitle")}
          body={t("properties.deleteBody")}
          confirmLabel={t("common.delete")}
          busy={remove.isPending}
          onCancel={() => setConfirming(false)}
          onConfirm={() =>
            remove.mutate(data.id, {
              onSuccess: () => navigate("/properties", { replace: true }),
              onError: () => setConfirming(false),
            })
          }
        />
      ) : null}
      <ErrorAlert error={remove.error} />
    </>
  );
}
