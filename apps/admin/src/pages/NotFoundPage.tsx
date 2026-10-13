import { Link } from "react-router-dom";

import { Empty } from "../components/ui";
import { t } from "../i18n";

export function NotFoundPage() {
  return (
    <Empty>
      <p>{t("errors.not_found")}</p>
      <Link to="/">{t("nav.dashboard")}</Link>
    </Empty>
  );
}
