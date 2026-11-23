import { test } from "node:test";
import assert from "node:assert/strict";
import { closeSession, openSession, sessionUser } from "../src/auth/session.ts";
import { makeToken } from "../src/auth/token.ts";
import { canViewOrders } from "../src/auth/permissions.ts";

test("a session maps to the token's user", () => {
  const now = 1_700_000_000_000;
  const id = openSession(makeToken(7, now / 1000 + 60), now);
  assert.equal(sessionUser(id, now), 7);
  closeSession(id);
  assert.equal(sessionUser(id, now), undefined);
});

test("expired tokens are rejected", () => {
  assert.throws(() => openSession(makeToken(7, 10), 20_000));
});

test("customers only see their own orders", () => {
  assert.equal(canViewOrders("customer", 1, 2), false);
  assert.equal(canViewOrders("support", 1, 2), true);
});
