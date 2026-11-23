import { test } from "node:test";
import assert from "node:assert/strict";
import { importBatch } from "../src/importer.ts";

test("imports all records", async () => {
  const saved: number[] = [];
  const result = await importBatch([1, 2, 3], async (r) => { saved.push(r); });
  assert.deepEqual(result, { ok: true, imported: 3 });
  assert.deepEqual(saved, [1, 2, 3]);
});
