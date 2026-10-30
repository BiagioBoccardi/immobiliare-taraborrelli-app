import type { AdminProperty } from "@taraborrelli/api-client";
import { useState, type ChangeEvent } from "react";

import { useDeleteThreeDModel, useUploadThreeDModel } from "../api/queries";
import { t } from "../i18n";
import { ConfirmDialog, ErrorAlert } from "./ui";

export const MAX_MODEL_BYTES = 10 * 1024 * 1024;

/** Checks the file before uploading; the service checks it again by content. */
export function rejectedModel(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".glb")) {
    return t("model3d.rejectedType", { name: file.name });
  }
  if (file.size > MAX_MODEL_BYTES) return t("model3d.rejectedSize", { name: file.name });
  return null;
}

export function formatMegabytes(bytes: number): string {
  const value = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(
    bytes / (1024 * 1024),
  );
  return `${value} MB`;
}

export function ThreeDModelManager({ property }: { property: AdminProperty }) {
  const upload = useUploadThreeDModel(property.id);
  const remove = useDeleteThreeDModel(property.id);
  const [rejected, setRejected] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const model = property.three_d_model;
  const busy = upload.isPending || remove.isPending;

  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const problem = rejectedModel(file);
    setRejected(problem);
    if (problem === null) upload.mutate(file);
  };

  return (
    <section className="card">
      <h2>{t("model3d.title")}</h2>
      <div className="upload">
        <label className="button button-secondary" htmlFor="model-upload">
          {upload.isPending
            ? t("model3d.uploading")
            : model
              ? t("model3d.replace")
              : t("model3d.upload")}
        </label>
        <input
          id="model-upload"
          type="file"
          accept=".glb,model/gltf-binary"
          hidden
          disabled={busy}
          onChange={onFile}
        />
        <span className="hint">{t("model3d.hint")}</span>
      </div>
      {rejected ? (
        <div className="alert alert-error" role="alert">
          {rejected}
        </div>
      ) : null}
      <ErrorAlert error={upload.error ?? remove.error} />
      {model ? (
        <div className="row">
          <span>{t("model3d.current", { size: formatMegabytes(model.size_bytes) })}</span>
          <a className="button button-secondary button-small" href={model.url} download>
            {t("model3d.open")}
          </a>
          <button
            type="button"
            className="button button-danger button-small"
            disabled={busy}
            onClick={() => setConfirming(true)}
          >
            {t("model3d.delete")}
          </button>
        </div>
      ) : (
        <p className="muted">{t("model3d.empty")}</p>
      )}
      {confirming ? (
        <ConfirmDialog
          title={t("model3d.deleteTitle")}
          body={t("model3d.deleteBody")}
          confirmLabel={t("common.delete")}
          busy={remove.isPending}
          onCancel={() => setConfirming(false)}
          onConfirm={() => remove.mutate(undefined, { onSettled: () => setConfirming(false) })}
        />
      ) : null}
    </section>
  );
}
