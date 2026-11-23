import { test } from "node:test";
import assert from "node:assert/strict";
import { importBatch } from "../src/importer.ts";

test("a failing save is reported, not lost", async () => {
  const result = await importBatch([1, 2], async (r) => {
    if (r === 2) throw new Error("duplicate key");
  });
  assert.equal(result.ok, false);
  assert.equal(result.error, "duplicate key");
});

test("waits for slow saves before reporting success", async () => {
  let done = 0;
  const result = await importBatch([1, 2], async () => {
    await new Promise((resolve) => setTimeout(resolve, 20));
    done++;
  });
  assert.equal(result.ok, true);
  assert.equal(done, 2);
});
