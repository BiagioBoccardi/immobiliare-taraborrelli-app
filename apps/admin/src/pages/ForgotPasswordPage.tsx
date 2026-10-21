import logo from "@taraborrelli/theme/assets/logo.png";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useForgotPassword, useResetPassword } from "../api/queries";
import { PasswordInput } from "../components/PasswordInput";
import { ErrorAlert, Field } from "../components/ui";
import { t } from "../i18n";

type Step = "email" | "code" | "done";

/** "Password dimenticata": email, then the emailed code with the new password. */
export function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ code?: string; password?: string }>({});
  const [resent, setResent] = useState(false);
  const request = useForgotPassword();
  const reset = useResetPassword();

  const sendCode = (event?: FormEvent) => {
    event?.preventDefault();
    request.mutate(email.trim(), {
      onSuccess: () => {
        if (step === "code") setResent(true);
        setStep("code");
      },
    });
  };

  const save = (event: FormEvent) => {
    event.preventDefault();
    const found: { code?: string; password?: string } = {};
    if (!/^\d{6}$/.test(code.trim())) found.code = t("forgot.invalidCode");
    if (password.length < 10) found.password = t("forgot.shortPassword");
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    reset.mutate(
      { email: email.trim(), code: code.trim(), password },
      { onSuccess: () => setStep("done") },
    );
  };

  const brand = (title: string, subtitle: string) => (
    <div className="login-brand">
      <img className="login-logo" src={logo} alt={t("app.name")} />
      <h1>{title}</h1>
      <p className="muted">{subtitle}</p>
    </div>
  );

  if (step === "done") {
    return (
      <div className="login">
        <div className="card stack">
          {brand(t("forgot.doneTitle"), t("forgot.doneSubtitle"))}
          <Link to="/login" className="button button-primary">
            {t("login.submit")}
          </Link>
        </div>
      </div>
    );
  }

  if (step === "code") {
    return (
      <div className="login">
        <form className="card stack" onSubmit={save} noValidate>
          {brand(t("forgot.codeTitle"), t("forgot.codeSubtitle", { email: email.trim() }))}
          <ErrorAlert error={reset.error} />
          {resent ? <p className="muted">{t("forgot.resent")}</p> : null}
          <Field label={t("forgot.code")} htmlFor="code" error={errors.code}>
            <input
              id="code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              aria-invalid={Boolean(errors.code)}
              onChange={(e) => setCode(e.target.value)}
            />
          </Field>
          <Field label={t("forgot.newPassword")} htmlFor="new-password" error={errors.password}>
            <PasswordInput
              id="new-password"
              autoComplete="new-password"
              value={password}
              aria-invalid={Boolean(errors.password)}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <button type="submit" className="button button-primary" disabled={reset.isPending}>
            {reset.isPending ? t("forgot.saving") : t("forgot.save")}
          </button>
          <div className="login-links">
            <Link to="/login">{t("forgot.backToLogin")}</Link>
            <button
              type="button"
              className="link-button"
              disabled={request.isPending}
              onClick={() => sendCode()}
            >
              {t("forgot.resend")}
            </button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="login">
      <form className="card stack" onSubmit={sendCode} noValidate>
        {brand(t("forgot.title"), t("forgot.subtitle"))}
        <ErrorAlert error={request.error} />
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
        <button
          type="submit"
          className="button button-primary"
          disabled={request.isPending || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())}
        >
          {request.isPending ? t("forgot.sending") : t("forgot.send")}
        </button>
        <div className="login-links">
          <Link to="/login">{t("forgot.backToLogin")}</Link>
        </div>
      </form>
    </div>
  );
}
