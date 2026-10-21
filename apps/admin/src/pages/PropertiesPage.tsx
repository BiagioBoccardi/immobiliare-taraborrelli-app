import type { AdminProperty, BulkResult, Contract, PropertyStatus } from "@taraborrelli/api-client";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import {
  useBulkDelete,
  useBulkPublish,
  useDeleteProperty,
  useProperties,
  usePublishProperty,
} from "../api/queries";
import { PropertyStatusBadge } from "../components/badges";
import {
  ConfirmDialog,
  Empty,
  ErrorAlert,
  Field,
  Loading,
  PageHeader,
  Pagination,
  SuccessAlert,
} from "../components/ui";
import { hasTranslation, t, tEnum } from "../i18n";
import { formatDate, formatEuro } from "../utils/format";
import { CONTRACTS, PROPERTY_STATUSES } from "./propertyForm";

const PAGE_SIZE = 20;

type Pending =
  { kind: "publishAll" } | { kind: "deleteAll" } | { kind: "deleteOne"; property: AdminProperty };

/** The agency knows its properties by the management software (Reasoft) code. */
function shownRef(property: AdminProperty): string {
  return property.external_ref ?? property.reference;
}

/** "Non pubblicati: 3 (2 senza foto, 1 senza superficie)". */
function skippedSummary(result: BulkResult): string {
  const counts = new Map<string, number>();
  for (const item of result.skipped) counts.set(item.reason, (counts.get(item.reason) ?? 0) + 1);
  const parts = [...counts].map(([reason, count]) => {
    const key = `properties.skip.${reason}`;
    return `${count} ${hasTranslation(key) ? t(key) : reason}`;
  });
  return `${t("properties.bulkSkipped", { count: result.skipped.length })} (${parts.join(", ")}).`;
}

export function PropertiesPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const page = Number(params.get("page") ?? "1") || 1;
  const filters = {
    status: (params.get("status") as PropertyStatus | null) ?? undefined,
    contract: (params.get("contract") as Contract | null) ?? undefined,
    q: params.get("q") ?? undefined,
  };
  const [query, setQuery] = useState(filters.q ?? "");
  const properties = useProperties({ ...filters, page, size: PAGE_SIZE });
  const bulkPublish = useBulkPublish();
  const bulkDelete = useBulkDelete();
  const publishOne = usePublishProperty();
  const deleteOne = useDeleteProperty();
  const [pending, setPending] = useState<Pending | null>(null);
  const [notice, setNotice] = useState<string[] | null>(null);
  const total = properties.data?.total ?? 0;
  const actionError = bulkPublish.error ?? bulkDelete.error ?? publishOne.error ?? deleteOne.error;

  const resetActions = () => {
    setNotice(null);
    bulkPublish.reset();
    bulkDelete.reset();
    publishOne.reset();
    deleteOne.reset();
  };

  const publish = (property: AdminProperty) => {
    resetActions();
    publishOne.mutate(property.id, {
      onSuccess: () => setNotice([t("properties.publishedOne", { reference: shownRef(property) })]),
    });
  };

  const confirm = () => {
    if (!pending) return;
    resetActions();
    const close = { onSettled: () => setPending(null) };
    if (pending.kind === "publishAll") {
      bulkPublish.mutate(filters, {
        ...close,
        onSuccess: (result) =>
          setNotice([
            t("properties.bulkPublished", { count: result.done }),
            ...(result.skipped.length ? [skippedSummary(result)] : []),
          ]),
      });
    } else if (pending.kind === "deleteAll") {
      bulkDelete.mutate(filters, {
        ...close,
        onSuccess: (result) => {
          setNotice([t("properties.bulkDeleted", { count: result.done })]);
          update({ page: "" });
        },
      });
    } else {
      const { property } = pending;
      deleteOne.mutate(property.id, {
        ...close,
        onSuccess: () => setNotice([t("properties.deletedOne", { reference: shownRef(property) })]),
      });
    }
  };

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [name, value] of Object.entries(changes)) {
      if (value) next.set(name, value);
      else next.delete(name);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next);
  };

  const search = (event: FormEvent) => {
    event.preventDefault();
    update({ q: query.trim() });
  };

  return (
    <>
      <PageHeader
        title={t("properties.title")}
        actions={
          <>
            <button
              type="button"
              className="button"
              disabled={total === 0}
              onClick={() => setPending({ kind: "publishAll" })}
            >
              {t("properties.publishAll")}
            </button>
            <button
              type="button"
              className="button button-danger"
              disabled={total === 0}
              onClick={() => setPending({ kind: "deleteAll" })}
            >
              {t("properties.deleteAll")}
            </button>
            <Link to="/properties/import" className="button">
              {t("properties.import")}
            </Link>
            <Link to="/properties/photos" className="button">
              {t("properties.bulkPhotos")}
            </Link>
            <Link to="/properties/new" className="button button-primary">
              {t("properties.new")}
            </Link>
          </>
        }
      />
      <form className="filters" onSubmit={search}>
        <Field label={t("common.search")} htmlFor="q" className="grow">
          <input
            id="q"
            type="search"
            placeholder={t("properties.searchPlaceholder")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </Field>
        <Field label={t("leads.status")} htmlFor="status">
          <select
            id="status"
            value={filters.status ?? ""}
            onChange={(e) => update({ status: e.target.value })}
          >
            <option value="">{t("common.all")}</option>
            {PROPERTY_STATUSES.map((status) => (
              <option key={status} value={status}>
                {tEnum("propertyStatus", status)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("properties.contract")} htmlFor="contract">
          <select
            id="contract"
            value={filters.contract ?? ""}
            onChange={(e) => update({ contract: e.target.value })}
          >
            <option value="">{t("common.all")}</option>
            {CONTRACTS.map((contract) => (
              <option key={contract} value={contract}>
                {tEnum("contract", contract)}
              </option>
            ))}
          </select>
        </Field>
        <button type="submit" className="button button-secondary">
          {t("common.search")}
        </button>
      </form>

      {notice ? (
        <SuccessAlert>
          {notice.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </SuccessAlert>
      ) : null}
      <ErrorAlert error={actionError} />
      {properties.isPending ? <Loading /> : null}
      <ErrorAlert error={properties.error} />
      {properties.data ? (
        properties.data.items.length === 0 ? (
          <div className="table-wrapper">
            <Empty />
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th aria-label={t("properties.sectionPhotos")} />
                    <th>{t("properties.reference")}</th>
                    <th>{t("properties.titleField")}</th>
                    <th>{t("properties.contract")}</th>
                    <th>{t("properties.municipality")}</th>
                    <th>{t("properties.price")}</th>
                    <th>{t("leads.status")}</th>
                    <th>{t("properties.updated")}</th>
                    <th>{t("properties.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {properties.data.items.map((property) => {
                    const cover = property.photos[0];
                    return (
                      <tr
                        key={property.id}
                        className="clickable"
                        onClick={() => navigate(`/properties/${property.id}`)}
                      >
                        <td>
                          {cover ? (
                            <img className="thumb" src={cover.url} alt="" loading="lazy" />
                          ) : (
                            <div className="thumb" />
                          )}
                        </td>
                        <td>
                          {property.external_ref ?? (
                            <span className="muted" title={t("properties.noExternalRef")}>
                              {property.reference}
                            </span>
                          )}
                        </td>
                        <td>
                          <Link to={`/properties/${property.id}`}>{property.title}</Link>
                        </td>
                        <td>{tEnum("contract", property.contract)}</td>
                        <td>{property.municipality}</td>
                        <td className="nowrap">{formatEuro(property.price)}</td>
                        <td>
                          <PropertyStatusBadge status={property.status} />
                        </td>
                        <td>{formatDate(property.updated_at)}</td>
                        <td>
                          {/* Buttons act on the row without opening the property. */}
                          <div className="row-actions" onClick={(e) => e.stopPropagation()}>
                            {property.status === "draft" ? (
                              <button
                                type="button"
                                className="button button-small button-primary"
                                disabled={publishOne.isPending}
                                aria-label={`${t("properties.publish")} ${shownRef(property)}`}
                                onClick={() => publish(property)}
                              >
                                {t("properties.publish")}
                              </button>
                            ) : null}
                            <Link
                              to={`/properties/${property.id}`}
                              className="button button-small"
                              aria-label={`${t("properties.edit")} ${shownRef(property)}`}
                            >
                              {t("properties.edit")}
                            </Link>
                            <button
                              type="button"
                              className="button button-small button-danger"
                              aria-label={`${t("properties.delete")} ${shownRef(property)}`}
                              onClick={() => setPending({ kind: "deleteOne", property })}
                            >
                              {t("properties.delete")}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              size={PAGE_SIZE}
              total={properties.data.total}
              onChange={(next) => update({ page: String(next) })}
            />
          </>
        )
      ) : null}

      {pending ? (
        <ConfirmDialog
          title={
            pending.kind === "publishAll"
              ? t("properties.publishAllTitle", { count: total })
              : pending.kind === "deleteAll"
                ? t("properties.deleteAllTitle", { count: total })
                : t("properties.deleteTitle")
          }
          body={
            pending.kind === "publishAll"
              ? t("properties.publishAllBody")
              : pending.kind === "deleteAll"
                ? t("properties.deleteAllBody")
                : t("properties.deleteBody")
          }
          confirmLabel={
            pending.kind === "publishAll" ? t("properties.publishAll") : t("common.delete")
          }
          tone={pending.kind === "publishAll" ? "primary" : "danger"}
          busy={bulkPublish.isPending || bulkDelete.isPending || deleteOne.isPending}
          onCancel={() => setPending(null)}
          onConfirm={confirm}
        />
      ) : null}
    </>
  );
}
