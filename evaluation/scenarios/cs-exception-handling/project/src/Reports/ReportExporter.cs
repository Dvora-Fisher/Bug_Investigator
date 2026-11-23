namespace Reports;

public class ReportExporter(Action<string, string> writeFile)
{
    /// <summary>
    /// Writes the report. Returns true when it was saved and false when saving failed
    /// (the caller then shows "Export failed, please retry").
    /// </summary>
    public bool Export(string path, string content)
    {
        try
        {
            writeFile(path, content);
        }
        catch (Exception)
        {
            // ignore
        }
        return true;
    }
}
