import type { AdminProperty } from "@taraborrelli/api-client";

import { ACCEPTED_TYPES, MAX_PHOTO_BYTES } from "../components/PhotoManager";

/** Same limit as the property service (MAX_PHOTOS_PER_PROPERTY). */
export const MAX_PHOTOS_PER_PROPERTY = 40;
/** Photos above this size or side are reduced before uploading (faster, lighter app). */
export const RESIZE_ABOVE_BYTES = 3 * 1024 * 1024;
export const MAX_SIDE = 2560;

export type UnmatchedReason = "no_property" | "unsupported_type";

export interface Unmatched {
  path: string;
  reason: UnmatchedReason;
}

export interface PhotoGroup {
  property: AdminProperty;
  files: File[];
  /** The property already has photos and "skip" was chosen: nothing is uploaded. */
  skipped: boolean;
  /** Files beyond the per-property limit, left out. */
  overLimit: number;
}

export interface BulkPhotoPlan {
  groups: PhotoGroup[];
  unmatched: Unmatched[];
}

// System files that are never photos: ignored without a message.
const IGNORED = /^(\.|thumbs\.db$|desktop\.ini$)/i;
const IMAGE_EXTENSIONS = /\.(jpe?g|png|webp|heic|heif|gif|bmp|tiff?)$/i;

/** "088" and "88" are the same code; letters are compared ignoring case. */
export function normalizeCode(code: string): string {
  const trimmed = code.trim().toLowerCase();
  return /^\d+$/.test(trimmed) ? String(Number.parseInt(trimmed, 10)) : trimmed;
}

/** "88 - Villa Oliveti" -> ["88 - villa oliveti", "88 - villa", ..., "88"]: longest first. */
function prefixes(text: string): string[] {
  const result = [text];
  for (let i = text.length - 1; i > 0; i--) {
    if (/[\s_\-.()[\]]/.test(text[i] ?? "")) {
      const prefix = text.slice(0, i).trim();
      if (prefix) result.push(prefix);
    }
  }
  return result;
}

/** Path shown to the user: "foto/88/1.jpg" when a folder was chosen, else the name. */
export function filePath(file: File): string {
  return file.webkitRelativePath || file.name;
}

/**
 * Finds the property of a photo from its path: first the folders (innermost first),
 * then the beginning of the file name.
 */
export function findCode(path: string, codes: Set<string>): string | null {
  const parts = path.split("/");
  const name = (parts.pop() ?? "").replace(/\.[^.]+$/, "");
  for (const segment of [...parts.reverse(), name]) {
    for (const candidate of prefixes(segment)) {
      const code = normalizeCode(candidate);
      if (codes.has(code)) return code;
    }
  }
  return null;
}

const byNaturalName = new Intl.Collator("it", { numeric: true, sensitivity: "base" });

export function planBulkPhotos(
  files: File[],
  properties: AdminProperty[],
  skipWithPhotos: boolean,
): BulkPhotoPlan {
  const byCode = new Map<string, AdminProperty>();
  for (const property of properties) {
    if (property.external_ref) byCode.set(normalizeCode(property.external_ref), property);
  }
  const codes = new Set(byCode.keys());
  const found = new Map<string, File[]>();
  const unmatched: Unmatched[] = [];

  for (const file of files) {
    const path = filePath(file);
    const name = path.split("/").pop() ?? "";
    if (IGNORED.test(name) || !(file.type.startsWith("image/") || IMAGE_EXTENSIONS.test(name))) {
      continue;
    }
    if (!ACCEPTED_TYPES.includes(file.type)) {
      unmatched.push({ path, reason: "unsupported_type" });
      continue;
    }
    const code = findCode(path, codes);
    if (code === null) {
      unmatched.push({ path, reason: "no_property" });
      continue;
    }
    found.set(code, [...(found.get(code) ?? []), file]);
  }

  const groups = [...found].map(([code, list]) => {
    const property = byCode.get(code) as AdminProperty;
    const sorted = [...list].sort((a, b) => byNaturalName.compare(filePath(a), filePath(b)));
    const room = Math.max(0, MAX_PHOTOS_PER_PROPERTY - property.photos.length);
    return {
      property,
      files: sorted.slice(0, room),
      skipped: skipWithPhotos && property.photos.length > 0,
      overLimit: Math.max(0, sorted.length - room),
    };
  });
  groups.sort((a, b) => byNaturalName.compare(a.property.reference, b.property.reference));
  return { groups, unmatched };
}

/**
 * Big camera photos are reduced to at most 2560 px and saved as JPEG in the browser.
 * Returns the file unchanged when it is already light or the browser cannot do it.
 */
export async function shrinkPhoto(file: File): Promise<Blob> {
  if (file.size <= RESIZE_ABOVE_BYTES || typeof createImageBitmap !== "function") return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.85),
    );
    return blob && blob.size < file.size ? blob : file;
  } catch {
    return file;
  }
}

export function isTooLarge(blob: Blob): boolean {
  return blob.size > MAX_PHOTO_BYTES;
}
