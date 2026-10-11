using System.Text.Json.Serialization;

namespace BookSpineTextRecognition;

public sealed class StructuredResult
{
    [JsonPropertyName("images")]
    public List<ImageResult> Images { get; set; } = [];
}

public sealed class ImageResult
{
    [JsonPropertyName("image")]
    public string Image { get; set; } = string.Empty;

    [JsonPropertyName("books")]
    public List<BookResult> Books { get; set; } = [];
}

public sealed class BookResult
{
    [JsonPropertyName("id")]
    public int? Id { get; set; }

    [JsonPropertyName("text")]
    public string Text { get; set; } = string.Empty;

    [JsonPropertyName("confidence")]
    public double Confidence { get; set; }

    [JsonPropertyName("quality")]
    public string Quality { get; set; } = string.Empty;

    [JsonPropertyName("direction")]
    public string Direction { get; set; } = string.Empty;
}

public sealed class BookResultView
{
    public int Id { get; init; }
    public string Text { get; init; } = "（未识别）";
    public string Confidence { get; init; } = "0.000";
    public string Quality { get; init; } = string.Empty;
    public string Direction { get; init; } = string.Empty;
}

public sealed class PipelineRunResult
{
    public required StructuredResult Structured { get; init; }
    public required string AnnotatedImagePath { get; init; }
    public required string TemporaryRoot { get; init; }
}
