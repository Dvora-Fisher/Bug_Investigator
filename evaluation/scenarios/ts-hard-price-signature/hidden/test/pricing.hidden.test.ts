import { test } from "node:test";
import assert from "node:assert/strict";
import { cartSummary } from "../src/cart.ts";
import { invoiceLines } from "../src/invoice.ts";
import { confirmationLine } from "../src/email.ts";
import { formatPrice } from "../src/format.ts";

test("cart page shows formatted prices", () => {
  assert.deepEqual(cartSummary([{ name: "Mug", price: 9.99, qty: 2 }, { name: "Pen", price: 1.5, qty: 1 }], "USD"),
    ["2 x Mug: $19.98", "1 x Pen: $1.50", "Total: $21.48"]);
});

test("invoice shows formatted prices", () => {
  assert.deepEqual(invoiceLines({ number: "INV-7", currency: "EUR", lines: [{ description: "Plan", amount: 19.99 }] }),
    ["Invoice INV-7", "Plan: €19.99", "Total due: €19.99"]);
});

test("the v2 signature is kept for the callers that already use it", () => {
  assert.equal(formatPrice("USD", 19.99), "$19.99");
  assert.equal(confirmationLine("1", "ILS", 10), "Thanks for order #1. You paid ₪10.00.");
});
