import type { GetPage } from "../src/paging.ts";

/** Fake API: pages keyed by cursor (null = first page). Throws after 50 calls so a runaway
 *  loop fails fast instead of hanging the test run. */
export function fakeApi(pages: Record<string, { items: number[]; next: string | null }>): GetPage<number> {
  let calls = 0;
  return async (cursor) => {
    if (++calls > 50) throw new Error("more than 50 page requests - the loop is not advancing");
    const page = pages[cursor ?? "start"];
    if (!page) throw new Error(`unknown cursor ${cursor}`);
    return page;
  };
}
