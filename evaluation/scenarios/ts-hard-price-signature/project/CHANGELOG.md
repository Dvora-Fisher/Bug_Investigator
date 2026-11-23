# Changelog

## 2.0.0
- BREAKING: `formatPrice(amount, currency)` is now `formatPrice(currency, amount)`, to match the new
  payments SDK. Call sites must be updated. `email.ts` was migrated in this release.
- Added the ILS currency symbol.

## 1.3.0
- Unknown currencies are printed with their code, e.g. "GBP 3.50".
