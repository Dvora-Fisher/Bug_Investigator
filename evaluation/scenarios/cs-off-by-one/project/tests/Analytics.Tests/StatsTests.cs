using Analytics;
using Xunit;

public class StatsTests
{
    [Fact]
    public void AverageOfLastTwo() => Assert.Equal(3.5, Stats.AverageOfLast([1, 2, 3, 4], 2));

    [Fact]
    public void RejectsTooLargeK() => Assert.Throws<ArgumentOutOfRangeException>(() => Stats.AverageOfLast([1], 2));
}
