import { test } from "node:test";
import assert from "node:assert/strict";
import { fetchAll } from "../src/paging.ts";
import { fakeApi } from "./pages.ts";

test("follows cursors across three pages", { timeout: 2000 }, async () => {
  const api = fakeApi({
    start: { items: [1], next: "b" },
    b: { items: [2, 3], next: "c" },
    c: { items: [4], next: null },
  });
  assert.deepEqual(await fetchAll(api), [1, 2, 3, 4]);
});
