/** Paginated list, the shape returned by every list endpoint. */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface PageQuery {
  page?: number | undefined;
  size?: number | undefined;
}

export function pageCount(page: Pick<Page<unknown>, "total" | "size">): number {
  return page.size > 0 ? Math.max(1, Math.ceil(page.total / page.size)) : 1;
}
