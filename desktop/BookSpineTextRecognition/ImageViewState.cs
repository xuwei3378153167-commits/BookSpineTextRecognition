namespace BookSpineTextRecognition;

// Geometry is independent of WinUI so pointer anchoring and unconstrained pan
// can be checked without generating synthetic Windows input.
public sealed class ImageViewState
{
    public double Zoom { get; private set; } = 1;
    public double OffsetX { get; private set; }
    public double OffsetY { get; private set; }
    public void Reset() { Zoom = 1; OffsetX = OffsetY = 0; }
    public void Pan(double x, double y) { OffsetX += x; OffsetY += y; }
    public void ZoomAt(double factor, double anchorX, double anchorY, double viewportWidth, double viewportHeight)
    {
        var next = Math.Clamp(Zoom * factor, .25, 8);
        var ratio = next / Zoom;
        OffsetX = (anchorX - viewportWidth / 2) * (1 - ratio) + OffsetX * ratio;
        OffsetY = (anchorY - viewportHeight / 2) * (1 - ratio) + OffsetY * ratio;
        Zoom = next;
    }
}
