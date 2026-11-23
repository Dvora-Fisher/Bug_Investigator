namespace Finance;

public static class Money
{
    /// <summary>
    /// Rounds an amount to cents. Finance policy FIN-12: halves are rounded away from zero
    /// (2.345 becomes 2.35). v3.0 replaced the old hand-written rounding with Math.Round.
    /// </summary>
    public static decimal ToCents(decimal amount) => Math.Round(amount, 2);

    public static decimal LineTotal(decimal unitPrice, int quantity) => ToCents(unitPrice * quantity);
}
