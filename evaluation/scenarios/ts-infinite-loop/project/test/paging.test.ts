import { test } from "node:test";
import assert from "node:assert/strict";
import { fetchAll } from "../src/paging.ts";
import { fakeApi } from "./pages.ts";

test("single page", { timeout: 2000 }, async () => {
  assert.deepEqual(await fetchAll(fakeApi({ start: { items: [1, 2], next: null } })), [1, 2]);
});
