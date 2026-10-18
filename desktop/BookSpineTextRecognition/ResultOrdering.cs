namespace BookSpineTextRecognition;

public static class ResultOrdering
{
    public static IReadOnlyList<BookResultView> Sort(IEnumerable<BookResultView> rows, bool byConfidence, bool ascending)
    {
        var sorted = byConfidence
            ? ascending
                ? rows.OrderBy(row => !row.ConfidenceValue.HasValue).ThenBy(row => row.ConfidenceValue)
                : rows.OrderBy(row => !row.ConfidenceValue.HasValue).ThenByDescending(row => row.ConfidenceValue)
            : ascending ? rows.OrderBy(row => row.Id) : rows.OrderByDescending(row => row.Id);
        return sorted.ThenBy(row => row.Id).ToList();
    }
}
