import { test } from "node:test";
import assert from "node:assert/strict";
import { confirmationLine } from "../src/email.ts";

test("confirmation email shows the paid amount", () => {
  assert.equal(confirmationLine("1001", "EUR", 42), "Thanks for order #1001. You paid €42.00.");
});
