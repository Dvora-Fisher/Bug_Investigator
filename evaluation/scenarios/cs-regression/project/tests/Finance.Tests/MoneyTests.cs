using Finance;
using Xunit;

public class MoneyTests
{
    [Fact]
    public void RoundsDown() => Assert.Equal(1.23m, Money.ToCents(1.234m));

    [Fact]
    public void LineTotal() => Assert.Equal(7.50m, Money.LineTotal(2.50m, 3));
}
