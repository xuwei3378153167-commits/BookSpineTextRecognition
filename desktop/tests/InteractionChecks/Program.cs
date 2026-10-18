using BookSpineTextRecognition;

var checks = 0;
void Check(bool condition, string message)
{
    if (!condition) throw new Exception(message);
    checks++;
}
void Near(double actual, double expected, string message) => Check(Math.Abs(actual - expected) < 1e-8, message);

BookResultView[] rows = [
    new() { Id = 10, ConfidenceValue = .90141, Confidence = "0.901" },
    new() { Id = 2, ConfidenceValue = .7 },
    new() { Id = 1, ConfidenceValue = .90149, Confidence = "0.901" },
    new() { Id = 7, ConfidenceValue = .85 },
];
void Order(bool byConfidence, bool ascending, params int[] expected) => Check(
    ResultOrdering.Sort(rows, byConfidence, ascending).Select(x => x.Id).SequenceEqual(expected),
    $"Unexpected order: confidence={byConfidence}, ascending={ascending}");
Order(false, true, 1, 2, 7, 10);
Order(false, false, 10, 7, 2, 1);
Order(true, true, 2, 7, 10, 1);
Order(true, false, 1, 10, 7, 2);
Check(rows.Select(x => x.Id).SequenceEqual(new[] { 10, 2, 1, 7 }), "Sorting mutated source order");
Check(ResultOrdering.Sort([], true, false).Count == 0, "Empty results must sort safely");
var tied = ResultOrdering.Sort([new() { Id = 99, ConfidenceValue = .8 }, new() { Id = 3, ConfidenceValue = .8 }], true, false);
Check(tied.Select(x => x.Id).SequenceEqual(new[] { 3, 99 }), "Ties must use numeric ID");

var view = new ImageViewState();
view.Pan(5000, -4000);
Near(view.OffsetX, 5000, "Pan must not be clamped at image bounds");
Near(view.OffsetY, -4000, "Pan must work beyond the fitted image");
view.Reset();
Near(view.OffsetX, 0, "Fit resets horizontal offset");
Near(view.OffsetY, 0, "Fit resets vertical offset");
Near(view.Zoom, 1, "Fit resets zoom");
var random = new Random(42);
for (var i = 0; i < 200; i++)
{
    view.Pan(random.Next(-30, 31), random.Next(-30, 31));
    var x = random.Next(800); var y = random.Next(600);
    var imageX = (x - 400 - view.OffsetX) / view.Zoom;
    var imageY = (y - 300 - view.OffsetY) / view.Zoom;
    view.ZoomAt(i % 2 == 0 ? .03 : 100, x, y, 800, 600);
    Near((x - 400 - view.OffsetX) / view.Zoom, imageX, "Wheel zoom changed the image position under the pointer (X)");
    Near((y - 300 - view.OffsetY) / view.Zoom, imageY, "Wheel zoom changed the image position under the pointer (Y)");
    Check(view.Zoom is >= .25 and <= 8, "Zoom exceeded its limits");
}
Console.WriteLine($"PASS: {checks} geometry and ordering assertions");
