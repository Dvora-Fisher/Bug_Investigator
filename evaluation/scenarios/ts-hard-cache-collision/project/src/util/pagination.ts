/** Page numbers start at 1. */
export function pageBounds(page: number, pageSize: number): { offset: number; limit: number } {
  if (!Number.isInteger(page) || page < 1) {
    throw new RangeError(`invalid page ${page}`);
  }
  return { offset: (page - 1) * pageSize, limit: pageSize };
}

export function parsePage(raw: string | undefined): number {
  const page = Number(raw ?? "1");
  return Number.isInteger(page) && page >= 1 ? page : 1;
}
