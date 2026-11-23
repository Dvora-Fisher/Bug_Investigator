/** Sum of amounts, rounded to cents to avoid long float tails such as 0.30000000000000004. */
export function sumAmounts(amounts: number[]): number {
  return Math.round(amounts.reduce((total, a) => total + a, 0) * 100) / 100;
}
