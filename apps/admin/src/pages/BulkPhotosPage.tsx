import { ApiError, type AdminProperty } from "@taraborrelli/api-client";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useApi } from "../api/ApiContext";
import { useAllProperties } from "../api/queries";
import { Badge, ErrorAlert, Field, Loading, PageHeader, SuccessAlert } from "../components/ui";
import { t, tError } from "../i18n";
import { filePath, isTooLarge, planBulkPhotos, shrinkPhoto, type PhotoGroup } from "./bulkPhotos";

/** Properties uploaded at the same time; the photos of one property go in order. */
const PARALLEL_PROPERTIES = 3;

interface Failure {
  reference: string;
  path: string;
  message: string;
}

interface Progress {
  total: number;
  done: number;
  failures: Failure[];
  finished: boolean;
}

export function BulkPhotosPage() {
  const api = useApi();
  const client = useQueryClient();
  const properties = useAllProperties();
  const [files, setFiles] = useState<File[]>([]);
  const [skipWithPhotos, setSkipWithPhotos] = useState(true);
  const [progress, setProgress] = useState<Progress | null>(null);
  const uploading = progress !== null && !progress.finished;

  const plan = useMemo(
    () => (properties.data ? planBulkPhotos(files, properties.data, skipWithPhotos) : null),
    [files, properties.data, skipWithPhotos],
  );
  const toUpload = plan ? plan.groups.filter((group) => !group.skipped) : [];
  const photoCount = toUpload.reduce((sum, group) => sum + group.files.length, 0);

  // Leaving the page would stop the upload half way: the browser asks first.
  useEffect(() => {
    if (!uploading) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [uploading]);

  const uploadGroup = async (group: PhotoGroup, report: (failure?: Failure) => void) => {
    for (const file of group.files) {
      const fail = (message: string) =>
        report({ reference: group.property.reference, path: filePath(file), message });
      try {
        const photo = await shrinkPhoto(file);
        if (isTooLarge(photo)) {
          fail(t("bulkPhotos.tooLarge"));
          continue;
        }
        await api.property.uploadPhoto(group.property.id, photo);
        report();
      } catch (error) {
        fail(tError(error instanceof ApiError ? error.code : undefined));
      }
    }
  };

  const start = async () => {
    const queue = [...toUpload];
    setProgress({ total: photoCount, done: 0, failures: [], finished: false });
    const report = (failure?: Failure) =>
      setProgress((current) =>
        current
          ? {
              ...current,
              done: current.done + 1,
              failures: failure ? [...current.failures, failure] : current.failures,
            }
          : current,
      );
    const worker = async () => {
      for (let group = queue.shift(); group; group = queue.shift()) {
        await uploadGroup(group, report);
      }
    };
    await Promise.all(Array.from({ length: PARALLEL_PROPERTIES }, worker));
    setProgress((current) => (current ? { ...current, finished: true } : current));
    setFiles([]);
    void client.invalidateQueries({ queryKey: ["properties"] });
  };

  const choose = (list: FileList | null) => {
    setProgress(null);
    setFiles(list ? Array.from(list) : []);
  };

  return (
    <>
      <PageHeader title={t("bulkPhotos.title")} subtitle={t("bulkPhotos.subtitle")} />

      <section className="card stack">
        <p>{t("bulkPhotos.howTo")}</p>
        <ul className="hint-list">
          <li>
            <code>foto/88/1.jpg</code> — {t("bulkPhotos.byFolder")}
          </li>
          <li>
            <code>88_1.jpg</code>, <code>88-2.jpg</code> — {t("bulkPhotos.byName")}
          </li>
        </ul>
        <p className="muted">{t("bulkPhotos.order")}</p>
        <div className="grid-2">
          <Field label={t("bulkPhotos.folder")} htmlFor="photo-folder">
            <input
              id="photo-folder"
              type="file"
              // Lets the browser pick a whole folder, subfolders included.
              {...{ webkitdirectory: "", directory: "" }}
              multiple
              disabled={uploading}
              onChange={(e) => choose(e.target.files)}
            />
          </Field>
          <Field label={t("bulkPhotos.files")} htmlFor="photo-files">
            <input
              id="photo-files"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              disabled={uploading}
              onChange={(e) => choose(e.target.files)}
            />
          </Field>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={skipWithPhotos}
            disabled={uploading}
            onChange={(e) => setSkipWithPhotos(e.target.checked)}
          />
          {t("bulkPhotos.skipWithPhotos")}
        </label>
      </section>

      {properties.isPending ? <Loading /> : null}
      <ErrorAlert error={properties.error} />

      {progress ? (
        <section className="card stack" aria-live="polite">
          <progress max={progress.total} value={progress.done} />
          <p>{t("bulkPhotos.progress", { done: progress.done, total: progress.total })}</p>
          {progress.finished ? (
            <SuccessAlert>
              <p>
                {t("bulkPhotos.done", {
                  count: progress.done - progress.failures.length,
                })}
              </p>
              <p className="row">
                <Link to="/properties?status=draft">{t("bulkPhotos.goToDrafts")}</Link>
              </p>
            </SuccessAlert>
          ) : null}
          {progress.failures.length > 0 ? (
            <div className="alert alert-error" role="alert">
              <p>{t("bulkPhotos.failures", { count: progress.failures.length })}</p>
              <ul>
                {progress.failures.map((failure) => (
                  <li key={`${failure.reference}-${failure.path}`}>
                    {failure.reference} · {failure.path}: {failure.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}

      {plan && files.length > 0 && !progress ? (
        <section className="card stack">
          <div className="row">
            <Badge tone="success">
              {t("bulkPhotos.summaryPhotos", { count: photoCount, properties: toUpload.length })}
            </Badge>
            {plan.unmatched.length > 0 ? (
              <Badge tone="danger">
                {t("bulkPhotos.summaryUnmatched", { count: plan.unmatched.length })}
              </Badge>
            ) : null}
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>{t("properties.reference")}</th>
                  <th>{t("properties.externalRef")}</th>
                  <th>{t("properties.titleField")}</th>
                  <th>{t("bulkPhotos.found")}</th>
                  <th>{t("bulkPhotos.outcome")}</th>
                </tr>
              </thead>
              <tbody>
                {plan.groups.map((group) => (
                  <GroupRow key={group.property.id} group={group} />
                ))}
              </tbody>
            </table>
          </div>

          {plan.unmatched.length > 0 ? (
            <details>
              <summary>{t("bulkPhotos.unmatchedTitle", { count: plan.unmatched.length })}</summary>
              <ul>
                {plan.unmatched.map((item) => (
                  <li key={item.path}>
                    {item.path}: {t(`bulkPhotos.reason.${item.reason}`)}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          <div className="row">
            {photoCount > 0 ? (
              <button type="button" className="button button-primary" onClick={() => void start()}>
                {t("bulkPhotos.upload", { count: photoCount })}
              </button>
            ) : (
              <span className="muted">{t("bulkPhotos.nothing")}</span>
            )}
          </div>
        </section>
      ) : null}
    </>
  );
}

function GroupRow({ group }: { group: PhotoGroup }) {
  const property: AdminProperty = group.property;
  return (
    <tr>
      <td>
        <Link to={`/properties/${property.id}`}>{property.reference}</Link>
      </td>
      <td>{property.external_ref}</td>
      <td>{property.title}</td>
      <td>{group.files.length}</td>
      <td>
        {group.skipped ? (
          <Badge>{t("bulkPhotos.hasPhotos", { count: property.photos.length })}</Badge>
        ) : (
          <Badge tone="success">{t("bulkPhotos.willUpload", { count: group.files.length })}</Badge>
        )}
        {group.overLimit > 0 ? (
          <span className="muted"> {t("bulkPhotos.overLimit", { count: group.overLimit })}</span>
        ) : null}
      </td>
    </tr>
  );
}
