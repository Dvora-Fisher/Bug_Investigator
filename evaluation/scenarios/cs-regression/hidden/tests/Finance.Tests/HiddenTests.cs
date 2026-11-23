using Finance;
using Xunit;

public class HiddenMoneyTests
{
    [Theory]
    [InlineData("2.345", "2.35")]
    [InlineData("2.355", "2.36")]
    [InlineData("-2.345", "-2.35")]
    [InlineData("1.234", "1.23")]
    public void HalvesRoundAwayFromZero(string input, string expected) =>
        Assert.Equal(decimal.Parse(expected), Money.ToCents(decimal.Parse(input)));
}
