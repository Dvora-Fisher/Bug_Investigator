namespace Analytics;

public static class Stats
{
    /// <summary>Average of the last k values (k must be between 1 and values.Length).</summary>
    public static double AverageOfLast(int[] values, int k)
    {
        if (k < 1 || k > values.Length)
        {
            throw new ArgumentOutOfRangeException(nameof(k));
        }

        double sum = 0;
        for (int i = values.Length - k; i <= values.Length; i++)
        {
            sum += values[i];
        }
        return sum / k;
    }
}
