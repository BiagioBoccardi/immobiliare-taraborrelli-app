import { Link } from "react-router-dom";

import { useLeads, useProperties } from "../api/queries";
import { PriorityBadge } from "../components/badges";
import { Empty, ErrorAlert, Loading, PageHeader } from "../components/ui";
import { t, tEnum } from "../i18n";
import { formatDateTime } from "../utils/format";

function Stat({ value, label, to }: { value: number | undefined; label: string; to: string }) {
  return (
    <Link to={to} className="card stat">
      <span className="stat-value">{value ?? "…"}</span>
      <span className="stat-label">{label}</span>
    </Link>
  );
}

/** The metrics that matter to the agency: owners to contact first, then the catalog. */
export function DashboardPage() {
  const newLeads = useLeads({ status: "new", size: 1 });
  const highPriority = useLeads({ status: "new", priority: "high", size: 1 });
  const due = useLeads({ due_for_contact: true, size: 5 });
  const published = useProperties({ status: "published", size: 1 });
  const drafts = useProperties({ status: "draft", size: 1 });

  return (
    <>
      <PageHeader title={t("dashboard.title")} />
      <div className="stack">
        <div className="grid-3">
          <Stat
            value={newLeads.data?.total}
            label={t("dashboard.newLeads")}
            to="/leads?status=new"
          />
          <Stat value={due.data?.total} label={t("dashboard.dueLeads")} to="/leads?due=1" />
          <Stat
            value={highPriority.data?.total}
            label={t("dashboard.highPriority")}
            to="/leads?status=new&priority=high"
          />
          <Stat
            value={published.data?.total}
            label={t("dashboard.published")}
            to="/properties?status=published"
          />
          <Stat
            value={drafts.data?.total}
            label={t("dashboard.drafts")}
            to="/properties?status=draft"
          />
        </div>

        <section className="card">
          <div className="page-header">
            <h2>{t("dashboard.dueList")}</h2>
            <Link to="/leads?due=1">{t("dashboard.seeAll")}</Link>
          </div>
          {due.isPending ? <Loading /> : null}
          <ErrorAlert error={due.error} />
          {due.data && due.data.items.length === 0 ? (
            <Empty>{t("dashboard.dueEmpty")}</Empty>
          ) : null}
          {due.data && due.data.items.length > 0 ? (
            <table>
              <tbody>
                {due.data.items.map((lead) => (
                  <tr key={lead.id}>
                    <td>
                      <Link to={`/leads/${lead.id}`}>{lead.full_name}</Link>
                    </td>
                    <td>{tEnum("leadKind", lead.kind)}</td>
                    <td>{lead.municipality}</td>
                    <td>
                      <PriorityBadge priority={lead.priority} />
                    </td>
                    <td>{formatDateTime(lead.next_contact_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>
      </div>
    </>
  );
}
