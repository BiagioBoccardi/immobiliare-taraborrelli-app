import type { Contract, PropertyStatus } from "@taraborrelli/api-client";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useProperties } from "../api/queries";
import { PropertyStatusBadge } from "../components/badges";
import { Empty, ErrorAlert, Field, Loading, PageHeader, Pagination } from "../components/ui";
import { t, tEnum } from "../i18n";
import { formatDate, formatEuro } from "../utils/format";
import { CONTRACTS, PROPERTY_STATUSES } from "./propertyForm";

const PAGE_SIZE = 20;

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
          <Link to="/properties/new" className="button button-primary">
            {t("properties.new")}
          </Link>
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
                        <td>{property.reference}</td>
                        <td>
                          <Link to={`/properties/${property.id}`}>{property.title}</Link>
                        </td>
                        <td>{tEnum("contract", property.contract)}</td>
                        <td>{property.municipality}</td>
                        <td>{formatEuro(property.price)}</td>
                        <td>
                          <PropertyStatusBadge status={property.status} />
                        </td>
                        <td>{formatDate(property.updated_at)}</td>
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
    </>
  );
}
