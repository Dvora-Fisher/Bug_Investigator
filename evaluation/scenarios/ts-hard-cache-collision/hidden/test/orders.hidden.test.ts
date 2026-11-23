import { test } from "node:test";
import assert from "node:assert/strict";
import { createApp } from "../src/app.ts";
import { openSession } from "../src/auth/session.ts";
import { makeToken } from "../src/auth/token.ts";
import { OrderRepo } from "../src/orders/orderRepo.ts";

function seed(repo: OrderRepo, userId: number, count: number, firstId: number) {
  for (let i = 0; i < count; i++) {
    repo.add({ id: firstId + i, userId, total: 1 + i, createdAt: "2026-02-01" });
  }
}

function twoUsers() {
  const repo = new OrderRepo();
  seed(repo, 1, 60, 1); // user 1 has 12 pages
  seed(repo, 11, 10, 1000); // user 11 has 2 pages
  return createApp(repo);
}

test("user 11 page 2 is not served from user 1 page 12", () => {
  const { orders } = twoUsers();
  assert.ok(orders.ordersPage(1, 12).every((o) => o.userId === 1));
  assert.deepEqual(orders.ordersPage(11, 2).map((o) => o.id), [1004, 1003, 1002, 1001, 1000]);
});

test("the same collision in the other order", () => {
  const { orders } = twoUsers();
  assert.ok(orders.ordersPage(11, 2).every((o) => o.userId === 11));
  assert.deepEqual(orders.ordersPage(1, 12).map((o) => o.id), [5, 4, 3, 2, 1]);
});

test("the endpoint never returns another user's orders", () => {
  const { route, orders } = twoUsers();
  orders.ordersPage(1, 12);
  const session = openSession(makeToken(11, Date.now() / 1000 + 600));
  const res = route("/me/orders", { ip: "2.2.2.2", headers: { "x-session": session }, query: { page: "2" } });
  assert.equal(res.status, 200);
  assert.ok((res.body as { userId: number }[]).every((o) => o.userId === 11));
});
