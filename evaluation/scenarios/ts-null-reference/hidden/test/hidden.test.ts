import { test } from "node:test";
import assert from "node:assert/strict";
import { displayName } from "../src/users.ts";

test("blank nickname falls back to the email name", () => {
  assert.equal(displayName({ id: 3, email: "noa@example.com", profile: { nickname: "   " } }), "noa");
});

test("profile without a nickname falls back to the email name", () => {
  assert.equal(displayName({ id: 4, email: "ron@example.com", profile: {} }), "ron");
});
