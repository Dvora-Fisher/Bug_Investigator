export interface Page<T> {
  items: T[];
  next: string | null; // cursor of the next page, null on the last page
}

export type GetPage<T> = (cursor: string | null) => Promise<Page<T>>;

/** Collect the items of every page, following `next` cursors until the last page. */
export async function fetchAll<T>(getPage: GetPage<T>): Promise<T[]> {
  const items: T[] = [];
  const cursor: string | null = null;
  let page: Page<T>;
  do {
    page = await getPage(cursor);
    items.push(...page.items);
  } while (page.next !== null);
  return items;
}
