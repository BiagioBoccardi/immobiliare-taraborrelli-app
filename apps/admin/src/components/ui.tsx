import { ApiError, pageCount } from "@taraborrelli/api-client";
import { useEffect, useId, useRef, type ReactNode } from "react";

import { t, tError } from "../i18n";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-title">
        <h1>{title}</h1>
        {subtitle ? <span className="muted">{subtitle}</span> : null}
      </div>
      {actions ? <div className="row">{actions}</div> : null}
    </header>
  );
}

export type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return <span className={tone === "neutral" ? "badge" : `badge badge-${tone}`}>{children}</span>;
}

export function Loading() {
  return (
    <p className="muted" role="status">
      {t("common.loading")}
    </p>
  );
}

/** Shows an API error with the message for its code. */
export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  const code = error instanceof ApiError ? error.code : undefined;
  return (
    <div className="alert alert-error" role="alert">
      {tError(code)}
    </div>
  );
}

export function SuccessAlert({ children }: { children: ReactNode }) {
  return (
    <div className="alert alert-success" role="status">
      {children}
    </div>
  );
}

export function Empty({ children }: { children?: ReactNode }) {
  return <div className="empty">{children ?? t("common.empty")}</div>;
}

export function Pagination({
  page,
  size,
  total,
  onChange,
}: {
  page: number;
  size: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = pageCount({ total, size });
  return (
    <nav className="pagination" aria-label="pagination">
      <span>{t("common.results", { total })}</span>
      <div className="row">
        <button
          type="button"
          className="button button-secondary button-small"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          {t("common.previous")}
        </button>
        <span>{t("common.page", { page, pages })}</span>
        <button
          type="button"
          className="button button-secondary button-small"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          {t("common.next")}
        </button>
      </div>
    </nav>
  );
}

export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  busy,
  tone = "danger",
  onConfirm,
  onCancel,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  busy?: boolean;
  /** "primary" for confirmations that do not destroy anything (e.g. publish). */
  tone?: "danger" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div className="dialog-backdrop">
      <div className="dialog" role="alertdialog" aria-modal="true" aria-labelledby={titleId}>
        <h2 id={titleId}>{title}</h2>
        <p>{body}</p>
        <div className="dialog-actions">
          <button
            ref={cancelRef}
            type="button"
            className="button button-secondary"
            onClick={onCancel}
          >
            {t("common.cancel")}
          </button>
          <button
            type="button"
            className={tone === "danger" ? "button button-danger" : "button button-primary"}
            disabled={busy}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
  className,
}: {
  label: string;
  hint?: string;
  error?: string | undefined;
  children: ReactNode;
  htmlFor: string;
  className?: string;
}) {
  return (
    <div className={className ? `field ${className}` : "field"}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint ? <span className="hint">{hint}</span> : null}
      {error ? <span className="field-error">{error}</span> : null}
    </div>
  );
}
