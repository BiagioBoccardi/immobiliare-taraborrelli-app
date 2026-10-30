import { ApiError, type OmiImportResult, type OmiWarning } from "@taraborrelli/api-client";
import { useState, type FormEvent } from "react";

import { useCurrentOmi, useImportOmi } from "../api/queries";
import { ErrorAlert, Field, Loading, PageHeader, SuccessAlert } from "../components/ui";
import { t } from "../i18n";
import { formatDate } from "../utils/format";

const DOWNLOAD_STEPS = ["omi.step1", "omi.step2", "omi.step3", "omi.step4"] as const;

function WarningItem({ warning }: { warning: OmiWarning }) {
  const examples = warning.examples?.length ? ` (${warning.examples.join(", ")})` : "";
  return (
    <li>
      {t(`omi.warning.${warning.code}`, { count: warning.count })}
      {examples}
    </li>
  );
}

function ImportOutcome({ result }: { result: OmiImportResult }) {
  return (
    <SuccessAlert>
      <p>
        {t("omi.done", { semester: result.semester, zones: result.zones, quotes: result.quotes })}
      </p>
      {result.warnings.length > 0 ? (
        <ul className="hint-list">
          {result.warnings.map((warning) => (
            <WarningItem key={warning.code} warning={warning} />
          ))}
        </ul>
      ) : null}
    </SuccessAlert>
  );
}

export function OmiPage() {
  const current = useCurrentOmi();
  const upload = useImportOmi();
  const [quotes, setQuotes] = useState<File | null>(null);
  const [zones, setZones] = useState<File | null>(null);
  const [perimeters, setPerimeters] = useState<File[]>([]);
  const [inputKey, setInputKey] = useState(0);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!quotes || perimeters.length === 0) return;
    upload.mutate(
      { quotes, zones: zones ?? undefined, perimeters },
      {
        onSuccess: () => {
          setQuotes(null);
          setZones(null);
          setPerimeters([]);
          setInputKey((key) => key + 1);
        },
      },
    );
  };

  return (
    <>
      <PageHeader title={t("omi.title")} subtitle={t("omi.subtitle")} />

      <section className="card stack">
        <h2>{t("omi.current")}</h2>
        {current.isPending ? <Loading /> : null}
        <ErrorAlert error={current.error} />
        {current.data === null ? (
          <div className="alert alert-error" role="status">
            {t("omi.none")}
          </div>
        ) : null}
        {current.data ? (
          <dl className="facts">
            <dt>{t("omi.semester")}</dt>
            <dd>{current.data.semester || t("common.none")}</dd>
            <dt>{t("omi.importedAt")}</dt>
            <dd>{formatDate(current.data.imported_at)}</dd>
            <dt>{t("omi.zones")}</dt>
            <dd>{current.data.zones}</dd>
            <dt>{t("omi.municipalities")}</dt>
            <dd>{current.data.municipalities.join(", ") || t("common.none")}</dd>
          </dl>
        ) : null}
        <p className="muted">{t("omi.howItWorks")}</p>
      </section>

      <section className="card stack">
        <h2>{t("omi.download")}</h2>
        <ol className="hint-list">
          {DOWNLOAD_STEPS.map((step) => (
            <li key={step}>{t(step)}</li>
          ))}
        </ol>
        <p className="muted">{t("omi.everySemester")}</p>
      </section>

      <form className="card stack" onSubmit={submit}>
        <h2>{t("omi.upload")}</h2>
        {upload.data ? <ImportOutcome result={upload.data} /> : null}
        <Field label={t("omi.quotesFile")} htmlFor="omi-quotes" hint={t("omi.quotesHint")}>
          <input
            key={`q${inputKey}`}
            id="omi-quotes"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setQuotes(e.target.files?.[0] ?? null)}
          />
        </Field>
        <Field label={t("omi.zonesFile")} htmlFor="omi-zones" hint={t("omi.zonesHint")}>
          <input
            key={`z${inputKey}`}
            id="omi-zones"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setZones(e.target.files?.[0] ?? null)}
          />
        </Field>
        <Field
          label={t("omi.perimetersFile")}
          htmlFor="omi-perimeters"
          hint={t("omi.perimetersHint")}
        >
          <input
            key={`p${inputKey}`}
            id="omi-perimeters"
            type="file"
            accept=".kmz,.kml,application/vnd.google-earth.kmz,application/vnd.google-earth.kml+xml"
            multiple
            onChange={(e) => setPerimeters(e.target.files ? Array.from(e.target.files) : [])}
          />
        </Field>
        <ErrorAlert error={upload.error} />
        {upload.error instanceof ApiError && typeof upload.error.details.file === "string" ? (
          <p className="muted">{t("omi.errorFile", { file: upload.error.details.file })}</p>
        ) : null}
        <div className="row">
          <button
            type="submit"
            className="button button-primary"
            disabled={!quotes || perimeters.length === 0 || upload.isPending}
          >
            {upload.isPending ? t("omi.uploading") : t("omi.submit")}
          </button>
        </div>
        <p className="muted">{t("omi.source")}</p>
      </form>
    </>
  );
}
