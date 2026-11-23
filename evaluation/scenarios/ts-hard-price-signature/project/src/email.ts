import { formatPrice } from "./format.ts";

/** Line in the order-confirmation email. */
export function confirmationLine(orderId: string, currency: string, total: number): string {
  return `Thanks for order #${orderId}. You paid ${formatPrice(currency, total)}.`;
}
