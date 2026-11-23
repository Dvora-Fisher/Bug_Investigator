using Analytics;
using Xunit;

public class HiddenStatsTests
{
    [Fact]
    public void WholeArray() => Assert.Equal(2.0, Stats.AverageOfLast([1, 2, 3], 3));

    [Fact]
    public void LastOne() => Assert.Equal(9.0, Stats.AverageOfLast([5, 9], 1));
}
