const SYMBOLS: Record<string, string> = { USD: "$", EUR: "€", ILS: "₪" };

/** v2.0.0: currency comes first (see CHANGELOG). Unknown currencies are printed with their code. */
export function formatPrice(currency: string, amount: number): string {
  const symbol = SYMBOLS[currency] ?? `${currency} `;
  return `${symbol}${Number(amount).toFixed(2)}`;
}
