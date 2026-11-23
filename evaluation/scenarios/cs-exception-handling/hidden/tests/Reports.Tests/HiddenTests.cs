using Reports;
using Xunit;

public class HiddenReportExporterTests
{
    [Fact]
    public void DiskFullReturnsFalse() =>
        Assert.False(new ReportExporter((_, _) => throw new IOException("No space left on device")).Export("a.csv", "x"));

    [Fact]
    public void AccessDeniedReturnsFalse() =>
        Assert.False(new ReportExporter((_, _) => throw new UnauthorizedAccessException()).Export("a.csv", "x"));
}
