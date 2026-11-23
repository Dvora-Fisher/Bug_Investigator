import { formatPrice } from "./format.ts";
import { sumAmounts } from "./money.ts";

export interface CartItem {
  name: string;
  price: number;
  qty: number;
}

export function cartTotal(items: CartItem[]): number {
  return sumAmounts(items.map((i) => i.price * i.qty));
}

/** Lines shown on the cart page. */
export function cartSummary(items: CartItem[], currency: string): string[] {
  const lines = items.map((i) => `${i.qty} x ${i.name}: ${formatPrice(i.price * i.qty, currency)}`);
  lines.push(`Total: ${formatPrice(cartTotal(items), currency)}`);
  return lines;
}
