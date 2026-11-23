import { test } from "node:test";
import assert from "node:assert/strict";
import { pageBounds, parsePage } from "../src/util/pagination.ts";
import { TtlCache } from "../src/cache/cache.ts";

test("page 1 starts at offset 0", () => {
  assert.deepEqual(pageBounds(1, 5), { offset: 0, limit: 5 });
  assert.deepEqual(pageBounds(3, 5), { offset: 10, limit: 5 });
});

test("bad page numbers fall back to 1", () => {
  assert.equal(parsePage(undefined), 1);
  assert.equal(parsePage("-2"), 1);
  assert.equal(parsePage("4"), 4);
});

test("cache entries expire after the ttl", () => {
  let now = 1000;
  const cache = new TtlCache<number>(100, () => now);
  cache.set("a", 1);
  assert.equal(cache.get("a"), 1);
  now = 1100;
  assert.equal(cache.get("a"), undefined);
});
