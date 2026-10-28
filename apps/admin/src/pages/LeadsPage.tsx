import type { LeadKind, LeadPriority, LeadStatus } from "@taraborrelli/api-client";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useLeads } from "../api/queries";
import { LeadStatusBadge, PriorityBadge } from "../components/badges";
import { Empty, ErrorAlert, Field, Loading, PageHeader, Pagination } from "../components/ui";
import { t, tEnum } from "../i18n";
import { formatDateTime } from "../utils/format";

const KINDS: LeadKind[] = ["valuation", "sell", "rent", "callback"];
const STATUSES: LeadStatus[] = [
  "new",
  "contacted",
  "appointment_scheduled",
  "mandate_acquired",
  "lost",
];
const PRIORITIES: LeadPriority[] = ["high", "medium", "low"];
const PAGE_SIZE = 20;

export function LeadsPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const page = Number(params.get("page") ?? "1") || 1;
  const filters = {
    kind: (params.get("kind") as LeadKind | null) ?? undefined,
    status: (params.get("status") as LeadStatus | null) ?? undefined,
    priority: (params.get("priority") as LeadPriority | null) ?? undefined,
    due_for_contact: params.get("due") === "1" || undefined,
  };
  const leads = useLeads({ ...filters, page, size: PAGE_SIZE });

  const setFilter = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    next.delete("page");
    setParams(next);
  };

  const setPage = (next: number) => {
    const updated = new URLSearchParams(params);
    updated.set("page", String(next));
    setParams(updated);
  };

  return (
    <>
      <PageHeader title={t("leads.title")} />
      <div className="filters">
        <Field label={t("leads.kind")} htmlFor="kind">
          <select
            id="kind"
            value={filters.kind ?? ""}
            onChange={(e) => setFilter("kind", e.target.value)}
          >
            <option value="">{t("common.all")}</option>
            {KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {tEnum("leadKind", kind)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("leads.status")} htmlFor="status">
          <select
            id="status"
            value={filters.status ?? ""}
            onChange={(e) => setFilter("status", e.target.value)}
          >
            <option value="">{t("common.all")}</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {tEnum("leadStatus", status)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("leads.priority")} htmlFor="priority">
          <select
            id="priority"
            value={filters.priority ?? ""}
            onChange={(e) => setFilter("priority", e.target.value)}
          >
            <option value="">{t("common.all")}</option>
            {PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {tEnum("leadPriority", priority)}
              </option>
            ))}
          </select>
        </Field>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={Boolean(filters.due_for_contact)}
            onChange={(e) => setFilter("due", e.target.checked ? "1" : "")}
          />
          {t("leads.dueOnly")}
        </label>
      </div>

      {leads.isPending ? <Loading /> : null}
      <ErrorAlert error={leads.error} />
      {leads.data ? (
        leads.data.items.length === 0 ? (
          <div className="table-wrapper">
            <Empty />
          </div>
        ) : (
          <>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>{t("leads.date")}</th>
                    <th>{t("leads.owner")}</th>
                    <th>{t("leads.kind")}</th>
                    <th>{t("leads.municipality")}</th>
                    <th>{t("leads.priority")}</th>
                    <th>{t("leads.status")}</th>
                    <th>{t("leads.nextContact")}</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.data.items.map((lead) => (
                    <tr
                      key={lead.id}
                      className="clickable"
                      onClick={() => navigate(`/leads/${lead.id}`)}
                    >
                      <td>{formatDateTime(lead.created_at)}</td>
                      <td>
                        <a href={`/leads/${lead.id}`} onClick={(e) => e.preventDefault()}>
                          {lead.full_name}
                        </a>
                      </td>
                      <td>{tEnum("leadKind", lead.kind)}</td>
                      <td>{lead.municipality ?? t("common.none")}</td>
                      <td>
                        <PriorityBadge priority={lead.priority} />
                      </td>
                      <td>
                        <LeadStatusBadge status={lead.status} />
                      </td>
                      <td>{formatDateTime(lead.next_contact_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} size={PAGE_SIZE} total={leads.data.total} onChange={setPage} />
          </>
        )
      ) : null}
    </>
  );
}
