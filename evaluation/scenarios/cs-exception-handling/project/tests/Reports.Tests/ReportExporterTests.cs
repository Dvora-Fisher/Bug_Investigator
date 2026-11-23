using Reports;
using Xunit;

public class ReportExporterTests
{
    [Fact]
    public void SuccessfulWriteReturnsTrue()
    {
        var written = new Dictionary<string, string>();
        Assert.True(new ReportExporter((p, c) => written[p] = c).Export("a.csv", "x"));
        Assert.Equal("x", written["a.csv"]);
    }
}
