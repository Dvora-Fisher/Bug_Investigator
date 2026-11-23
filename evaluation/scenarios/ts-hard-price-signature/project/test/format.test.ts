import { test } from "node:test";
import assert from "node:assert/strict";
import { formatPrice } from "../src/format.ts";
import { sumAmounts } from "../src/money.ts";

test("formats known currencies with their symbol", () => {
  assert.equal(formatPrice("USD", 5), "$5.00");
  assert.equal(formatPrice("ILS", 12.5), "₪12.50");
});

test("unknown currencies use their code", () => {
  assert.equal(formatPrice("GBP", 3.5), "GBP 3.50");
});

test("sums amounts to cents", () => {
  assert.equal(sumAmounts([0.1, 0.2]), 0.3);
});
