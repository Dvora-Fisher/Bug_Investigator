import { test } from "node:test";
import assert from "node:assert/strict";
import { rankOf, topScores } from "../src/leaderboard.js";

test("input is not modified", () => {
  const scores = [3, 1000, 20];
  topScores(scores, 2);
  assert.deepEqual(scores, [3, 1000, 20]);
});

test("ranks use numeric order", () => {
  assert.equal(rankOf([10, 9, 200], 200), 1);
  assert.equal(rankOf([10, 9, 200], 9), 3);
});
