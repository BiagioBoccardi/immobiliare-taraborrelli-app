import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useSession, useSessionStore } from "../auth/SessionContext";
import { t, tEnum } from "../i18n";

export function Layout() {
  const { user } = useSession();
  const store = useSessionStore();
  const navigate = useNavigate();

  const logout = async () => {
    await store.logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-name">{t("app.name")}</span>
          <span className="brand-area">{t("app.area")}</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>
            {t("nav.dashboard")}
          </NavLink>
          <NavLink to="/leads">{t("nav.leads")}</NavLink>
          <NavLink to="/properties">{t("nav.properties")}</NavLink>
          {user?.role === "admin" ? <NavLink to="/users">{t("nav.users")}</NavLink> : null}
        </nav>
        <div className="sidebar-footer">
          {user ? (
            <>
              <strong>{user.full_name}</strong>
              <span>{tEnum("role", user.role)}</span>
            </>
          ) : null}
          <button type="button" className="button button-ghost button-small" onClick={logout}>
            {t("nav.logout")}
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
