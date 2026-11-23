import { test } from "node:test";
import assert from "node:assert/strict";
import { topScores } from "../src/leaderboard.js";

test("top three", () => {
  assert.deepEqual(topScores([5, 3, 8, 1], 3), [8, 5, 3]);
});

test("top scores with different digit counts", () => {
  assert.deepEqual(topScores([9, 100, 25, 7], 2), [100, 25]);
});
