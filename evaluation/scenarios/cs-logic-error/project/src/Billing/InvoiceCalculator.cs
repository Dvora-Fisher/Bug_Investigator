namespace Billing;

public record LineItem(string Sku, decimal UnitPrice, int Quantity);

public static class InvoiceCalculator
{
    public const decimal DiscountThreshold = 100m;
    public const decimal DiscountRate = 0.10m;

    /// <summary>
    /// Sum of all lines. Orders of DiscountThreshold or more get a DiscountRate discount.
    /// </summary>
    public static decimal Total(IEnumerable<LineItem> items)
    {
        decimal subtotal = 0m;
        foreach (var item in items)
        {
            subtotal += item.UnitPrice * item.Quantity;
        }

        if (subtotal > DiscountThreshold)
        {
            subtotal -= subtotal * DiscountRate;
        }

        return Math.Round(subtotal, 2);
    }
}
