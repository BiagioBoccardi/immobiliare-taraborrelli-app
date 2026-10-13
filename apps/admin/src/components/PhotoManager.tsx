import type { AdminProperty } from "@taraborrelli/api-client";
import { useState, type ChangeEvent } from "react";

import { useDeletePhoto, useReorderPhotos, useUpdatePhoto, useUploadPhoto } from "../api/queries";
import { t } from "../i18n";
import { ConfirmDialog, ErrorAlert } from "./ui";

export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

/** Checks files before uploading; the service checks them again by content. */
export function rejectedFiles(files: File[]): string[] {
  const messages: string[] = [];
  for (const file of files) {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      messages.push(t("photos.rejectedType", { name: file.name }));
    } else if (file.size > MAX_PHOTO_BYTES) {
      messages.push(t("photos.rejectedSize", { name: file.name }));
    }
  }
  return messages;
}

export function PhotoManager({ property }: { property: AdminProperty }) {
  const upload = useUploadPhoto(property.id);
  const update = useUpdatePhoto(property.id);
  const reorder = useReorderPhotos(property.id);
  const remove = useDeletePhoto(property.id);
  const [uploading, setUploading] = useState(0);
  const [rejected, setRejected] = useState<string[]>([]);
  const [deleting, setDeleting] = useState<string | null>(null);
  const photos = property.photos;

  const onFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    const problems = rejectedFiles(files);
    setRejected(problems);
    const valid = files.filter(
      (file) => ACCEPTED_TYPES.includes(file.type) && file.size <= MAX_PHOTO_BYTES,
    );
    // One at a time, so the order of the upload is the order of the photos.
    for (const [index, file] of valid.entries()) {
      setUploading(valid.length - index);
      try {
        await upload.mutateAsync(file);
      } catch {
        break; // the error is shown by ErrorAlert
      }
    }
    setUploading(0);
  };

  const move = (index: number, offset: -1 | 1) => {
    const ids = photos.map((photo) => photo.id);
    const target = index + offset;
    const current = ids[index];
    const other = ids[target];
    if (current === undefined || other === undefined) return;
    ids[index] = other;
    ids[target] = current;
    reorder.mutate(ids);
  };

  const busy = uploading > 0 || reorder.isPending || remove.isPending;

  return (
    <section className="card">
      <h2>{t("properties.sectionPhotos")}</h2>
      <div className="upload">
        <label className="button button-secondary" htmlFor="photo-upload">
          {uploading > 0 ? t("photos.uploading", { count: uploading }) : t("photos.upload")}
        </label>
        <input
          id="photo-upload"
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          multiple
          hidden
          disabled={busy}
          onChange={onFiles}
        />
        <span className="hint">{t("photos.hint")}</span>
      </div>
      {rejected.map((message) => (
        <div key={message} className="alert alert-error" role="alert">
          {message}
        </div>
      ))}
      <ErrorAlert error={upload.error ?? update.error ?? reorder.error ?? remove.error} />
      {photos.length === 0 ? (
        <p className="muted">{t("photos.empty")}</p>
      ) : (
        <div className="photo-grid">
          {photos.map((photo, index) => (
            <figure key={photo.id} className="photo">
              <img src={photo.url} alt={photo.caption ?? ""} loading="lazy" />
              {index === 0 ? <span className="badge badge-info">{t("photos.cover")}</span> : null}
              <input
                type="text"
                aria-label={t("photos.caption")}
                placeholder={t("photos.caption")}
                defaultValue={photo.caption ?? ""}
                maxLength={200}
                onBlur={(e) => {
                  const caption = e.target.value.trim();
                  if (caption !== (photo.caption ?? "")) {
                    update.mutate({ photoId: photo.id, caption });
                  }
                }}
              />
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={photo.show_when_sold}
                  onChange={(e) =>
                    update.mutate({ photoId: photo.id, show_when_sold: e.target.checked })
                  }
                />
                {t("photos.showWhenSold")}
              </label>
              <div className="row">
                <button
                  type="button"
                  className="button button-secondary button-small"
                  disabled={busy || index === 0}
                  onClick={() => move(index, -1)}
                >
                  {t("photos.moveLeft")}
                </button>
                <button
                  type="button"
                  className="button button-secondary button-small"
                  disabled={busy || index === photos.length - 1}
                  onClick={() => move(index, 1)}
                >
                  {t("photos.moveRight")}
                </button>
                <button
                  type="button"
                  className="button button-danger button-small"
                  disabled={busy}
                  onClick={() => setDeleting(photo.id)}
                >
                  {t("photos.delete")}
                </button>
              </div>
            </figure>
          ))}
        </div>
      )}
      {deleting ? (
        <ConfirmDialog
          title={t("photos.deleteTitle")}
          body={t("photos.deleteBody")}
          confirmLabel={t("common.delete")}
          busy={remove.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => remove.mutate(deleting, { onSettled: () => setDeleting(null) })}
        />
      ) : null}
    </section>
  );
}
