import { test } from "node:test";
import assert from "node:assert/strict";
import { displayName, listNames } from "../src/users.ts";

test("uses the nickname when present", () => {
  assert.equal(displayName({ id: 1, email: "dana@example.com", profile: { nickname: " Dee " } }), "Dee");
});

test("falls back to the email name without a profile", () => {
  assert.equal(displayName({ id: 2, email: "avi@example.com" }), "avi");
});

test("lists names for a mixed set of users", () => {
  assert.deepEqual(
    listNames([{ id: 1, email: "a@x.io", profile: {} }, { id: 2, email: "b@x.io" }]),
    ["a", "b"],
  );
});
