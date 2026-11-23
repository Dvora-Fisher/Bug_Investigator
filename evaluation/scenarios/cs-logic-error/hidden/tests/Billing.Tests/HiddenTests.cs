using Billing;
using Xunit;

public class HiddenInvoiceCalculatorTests
{
    [Fact]
    public void JustBelowThresholdHasNoDiscount() =>
        Assert.Equal(99.99m, InvoiceCalculator.Total([new LineItem("A", 99.99m, 1)]));

    [Fact]
    public void AboveThresholdGetsDiscount() =>
        Assert.Equal(135m, InvoiceCalculator.Total([new LineItem("A", 50m, 3)]));
}
