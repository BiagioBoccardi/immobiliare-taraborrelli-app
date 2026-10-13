import { ApiError } from "@taraborrelli/api-client";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useSession, useSessionStore } from "../auth/SessionContext";
import { Field } from "../components/ui";
import { t, tError } from "../i18n";

export function LoginPage() {
  const store = useSessionStore();
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from ?? "/";
  if (session.status === "authenticated") return <Navigate to={from} replace />;

  const sessionError =
    session.error === "not_staff"
      ? t("login.notStaff")
      : session.error === "unauthorized"
        ? tError("unauthorized")
        : null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await store.login(email, password);
      navigate(from, { replace: true });
    } catch (caught) {
      setError(tError(caught instanceof ApiError ? caught.code : undefined));
    } finally {
      setSubmitting(false);
    }
  };

  const message = error ?? sessionError;

  return (
    <div className="login">
      <form className="card stack" onSubmit={submit} noValidate>
        <div className="login-brand">
          <div className="brand-name">{t("app.name")}</div>
          <h1>{t("login.title")}</h1>
          <p className="muted">{t("login.subtitle")}</p>
        </div>
        {message ? (
          <div className="alert alert-error" role="alert">
            {message}
          </div>
        ) : null}
        <Field label={t("login.email")} htmlFor="email">
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label={t("login.password")} htmlFor="password">
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <button
          type="submit"
          className="button button-primary"
          disabled={submitting || !email || !password}
        >
          {submitting ? t("login.submitting") : t("login.submit")}
        </button>
      </form>
    </div>
  );
}
