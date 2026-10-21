import type { ImportIssue, ImportPreview, ImportResult, ImportRow } from "@taraborrelli/api-client";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useApi } from "../api/ApiContext";
import { usePreviewImport, useRunImport } from "../api/queries";
import {
  Badge,
  ErrorAlert,
  Field,
  PageHeader,
  SuccessAlert,
  type BadgeTone,
} from "../components/ui";
import { hasTranslation, t, tEnum, type TranslationKey } from "../i18n";
import { formatEuro } from "../utils/format";

/** Labels of the property fields, as in the property form. */
const FIELD_LABELS: Record<string, TranslationKey> = {
  external_ref: "properties.externalRef",
  contract: "properties.contract",
  property_type: "properties.type",
  title: "properties.titleField",
  description: "properties.description",
  price: "properties.price",
  condominium_fees: "properties.condominiumFees",
  surface_sqm: "properties.surface",
  rooms: "properties.rooms",
  bedrooms: "properties.bedrooms",
  bathrooms: "properties.bathrooms",
  floor: "properties.floor",
  total_floors: "properties.totalFloors",
  year_built: "properties.yearBuilt",
  condition: "properties.condition",
  energy_class: "properties.energyClass",
  features: "properties.features",
  municipality: "properties.municipality",
  zone: "properties.zone",
  address: "properties.address",
  latitude: "properties.latitude",
  longitude: "properties.longitude",
  available_from: "properties.availableFrom",
  is_featured: "properties.featured",
};

export function fieldLabel(field: string | null | undefined): string {
  if (!field) return "";
  if (field.startsWith("features.")) {
    return t("import.feature", { name: tEnum("feature", field.slice("features.".length)) });
  }
  const key = FIELD_LABELS[field];
  return key ? t(key) : field;
}

export function issueText(issue: ImportIssue): string {
  const key = `import.issue.${issue.code}`;
  const params = {
    field: issue.column ?? fieldLabel(issue.field),
    // The deduced contract comes as "sale"/"rent": show it in Italian.
    value:
      issue.code === "contract_inferred" ? tEnum("contract", issue.value) : (issue.value ?? ""),
  };
  return hasTranslation(key) ? t(key, params) : t("import.issue.generic", params);
}

const ACTION_TONE: Record<ImportRow["action"], BadgeTone> = {
  create: "success",
  update: "info",
  invalid: "danger",
};

function RowChecks({ row }: { row: ImportRow }) {
  if (row.errors.length === 0 && row.warnings.length === 0) {
    return <span className="muted">{t("import.noProblems")}</span>;
  }
  return (
    <ul className="issues">
      {row.errors.map((issue, index) => (
        <li key={`e${index}`} className="issue issue-error">
          {issueText(issue)}
        </li>
      ))}
      {row.warnings.map((issue, index) => (
        <li key={`w${index}`} className="issue issue-warning">
          {issueText(issue)}
        </li>
      ))}
    </ul>
  );
}

function PreviewReport({ preview }: { preview: ImportPreview }) {
  const [onlyProblems, setOnlyProblems] = useState(false);
  const rows = onlyProblems
    ? preview.rows.filter((row) => row.errors.length > 0 || row.warnings.length > 0)
    : preview.rows;

  return (
    <section className="card stack">
      <div className="row">
        <Badge tone="success">{t("import.summaryCreate", { count: preview.totals.create })}</Badge>
        <Badge tone="info">{t("import.summaryUpdate", { count: preview.totals.update })}</Badge>
        <Badge tone={preview.totals.invalid ? "danger" : "neutral"}>
          {t("import.summaryInvalid", { count: preview.totals.invalid })}
        </Badge>
      </div>

      {preview.missing_columns.length > 0 ? (
        <div className="alert alert-error" role="alert">
          {t("import.missingColumns", {
            columns: preview.missing_columns.map((field) => fieldLabel(field)).join(", "),
          })}
        </div>
      ) : null}

      <dl className="columns-map">
        <dt>{t("import.recognized")}</dt>
        <dd>
          {preview.columns.map((column) => (
            <span key={column.header} className="chip">
              {column.header} → {fieldLabel(column.field)}
            </span>
          ))}
        </dd>
        {preview.ignored_columns.length > 0 ? (
          <>
            <dt>{t("import.ignored")}</dt>
            <dd className="muted">{preview.ignored_columns.join(", ")}</dd>
          </>
        ) : null}
      </dl>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={onlyProblems}
          onChange={(e) => setOnlyProblems(e.target.checked)}
        />
        {t("import.onlyProblems")}
      </label>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>{t("import.row")}</th>
              <th>{t("import.reference")}</th>
              <th>{t("import.titleColumn")}</th>
              <th>{t("import.municipality")}</th>
              <th>{t("import.price")}</th>
              <th>{t("import.outcome")}</th>
              <th>{t("import.checks")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted">
                  {t("import.noRows")}
                </td>
              </tr>
            ) : null}
            {rows.map((row) => (
              <tr key={row.row}>
                <td>{row.row}</td>
                <td>{row.external_ref ?? "—"}</td>
                <td>{row.title ?? "—"}</td>
                <td>{row.municipality ?? "—"}</td>
                <td className="nowrap">{row.price === null ? "—" : formatEuro(row.price)}</td>
                <td>
                  <Badge tone={ACTION_TONE[row.action]}>{t(`import.action.${row.action}`)}</Badge>
                </td>
                <td>
                  <RowChecks row={row} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ImportPage() {
  const api = useApi();
  const [file, setFile] = useState<File | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [result, setResult] = useState<ImportResult | null>(null);
  const preview = usePreviewImport();
  const run = useRunImport();
  const [templateError, setTemplateError] = useState<unknown>(null);

  const importable = preview.data ? preview.data.totals.create + preview.data.totals.update : 0;

  const check = (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setResult(null);
    run.reset();
    preview.mutate(file);
  };

  const startImport = () => {
    if (!file) return;
    run.mutate(file, {
      onSuccess: (done) => {
        setResult(done);
        preview.reset();
        setFile(null);
        setInputKey((key) => key + 1);
      },
    });
  };

  const downloadTemplate = async () => {
    setTemplateError(null);
    try {
      const blob = await api.property.importTemplate();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "modello-importazione-immobili.xlsx";
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setTemplateError(error);
    }
  };

  return (
    <>
      <PageHeader
        title={t("import.title")}
        subtitle={t("import.subtitle")}
        actions={
          <button type="button" className="button" onClick={() => void downloadTemplate()}>
            {t("import.template")}
          </button>
        }
      />
      <ErrorAlert error={templateError} />

      {result ? (
        <SuccessAlert>
          <p>{t("import.done", { ...result })}</p>
          {result.created > 0 ? <p>{t("import.doneHint")}</p> : null}
          <p className="row">
            <Link to="/properties?status=draft">{t("import.goToDrafts")}</Link>
          </p>
        </SuccessAlert>
      ) : null}

      <form className="card stack" onSubmit={check}>
        <Field label={t("import.file")} htmlFor="import-file" hint={t("import.fileHint")}>
          <input
            key={inputKey}
            id="import-file"
            type="file"
            accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              preview.reset();
            }}
          />
        </Field>
        <p className="muted">{t("import.draftNote")}</p>
        <div className="row">
          <button
            type="submit"
            className="button button-primary"
            disabled={!file || preview.isPending}
          >
            {preview.isPending ? t("import.checking") : t("import.check")}
          </button>
        </div>
        <ErrorAlert error={preview.error} />
      </form>

      {preview.data ? (
        <>
          <PreviewReport preview={preview.data} />
          <div className="card row">
            {importable > 0 ? (
              <button
                type="button"
                className="button button-primary"
                disabled={run.isPending}
                onClick={startImport}
              >
                {run.isPending ? t("import.running") : t("import.run", { count: importable })}
              </button>
            ) : (
              <span className="muted">{t("import.nothingToImport")}</span>
            )}
          </div>
          <ErrorAlert error={run.error} />
        </>
      ) : null}
    </>
  );
}
