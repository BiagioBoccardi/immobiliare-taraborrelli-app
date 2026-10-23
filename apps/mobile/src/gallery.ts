/** Photos downloaded around the current one: on slow connections the visible photo comes first. */
const PRELOAD_AROUND = 1;

/** Indexes to download: the ones already seen plus the neighbors of the current photo. */
export function photosToLoad(
  seen: ReadonlySet<number>,
  current: number,
  total: number,
): Set<number> {
  const result = new Set(seen);
  for (let i = current - PRELOAD_AROUND; i <= current + PRELOAD_AROUND; i++) {
    if (i >= 0 && i < total) result.add(i);
  }
  return result;
}
