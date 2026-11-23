import { test } from "node:test";
import assert from "node:assert/strict";
import { createApp } from "../src/app.ts";
import { openSession } from "../src/auth/session.ts";
import { makeToken } from "../src/auth/token.ts";
import { OrderRepo } from "../src/orders/orderRepo.ts";

function seed(repo: OrderRepo, userId: number, count: number, firstId: number) {
  for (let i = 0; i < count; i++) {
    repo.add({ id: firstId + i, userId, total: 10 + i, createdAt: "2026-01-01" });
  }
}

test("orders are paged newest first", () => {
  const repo = new OrderRepo();
  seed(repo, 4, 7, 1);
  const { orders } = createApp(repo);
  assert.deepEqual(orders.ordersPage(4, 1).map((o) => o.id), [7, 6, 5, 4, 3]);
  assert.deepEqual(orders.ordersPage(4, 2).map((o) => o.id), [2, 1]);
  assert.deepEqual(orders.ordersPage(4, 1).map((o) => o.id), [7, 6, 5, 4, 3]); // from the cache
});

test("the endpoint returns the signed-in user's orders", () => {
  const repo = new OrderRepo();
  seed(repo, 3, 2, 1);
  seed(repo, 5, 2, 10);
  const { route } = createApp(repo);
  const session = openSession(makeToken(5, Date.now() / 1000 + 600));
  const res = route("/me/orders", { ip: "1.1.1.1", headers: { "x-session": session }, query: {} });
  assert.equal(res.status, 200);
  assert.deepEqual((res.body as { userId: number }[]).map((o) => o.userId), [5, 5]);
});

test("anonymous requests get 401", () => {
  const { route } = createApp();
  assert.equal(route("/me/orders", { ip: "1.1.1.2", headers: {}, query: {} }).status, 401);
});
