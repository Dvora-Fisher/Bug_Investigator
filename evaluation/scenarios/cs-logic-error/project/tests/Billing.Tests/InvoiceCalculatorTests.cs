using Billing;
using Xunit;

public class InvoiceCalculatorTests
{
    [Fact]
    public void SmallOrderHasNoDiscount() =>
        Assert.Equal(50m, InvoiceCalculator.Total([new LineItem("A", 25m, 2)]));

    [Fact]
    public void LargeOrderGetsTenPercentOff() =>
        Assert.Equal(180m, InvoiceCalculator.Total([new LineItem("A", 100m, 2)]));

    [Fact]
    public void OrderOfExactlyOneHundredGetsTheDiscount() =>
        Assert.Equal(90m, InvoiceCalculator.Total([new LineItem("A", 50m, 1), new LineItem("B", 25m, 2)]));
}
