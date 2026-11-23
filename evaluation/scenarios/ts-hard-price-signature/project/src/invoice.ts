import { formatPrice } from "./format.ts";
import { sumAmounts } from "./money.ts";

export interface InvoiceLine {
  description: string;
  amount: number;
}

export interface Invoice {
  number: string;
  currency: string;
  lines: InvoiceLine[];
}

/** Text lines rendered into the PDF invoice. */
export function invoiceLines(invoice: Invoice): string[] {
  const rows = invoice.lines.map((l) => `${l.description}: ${formatPrice(l.amount, invoice.currency)}`);
  const total = sumAmounts(invoice.lines.map((l) => l.amount));
  return [`Invoice ${invoice.number}`, ...rows, `Total due: ${formatPrice(total, invoice.currency)}`];
}
