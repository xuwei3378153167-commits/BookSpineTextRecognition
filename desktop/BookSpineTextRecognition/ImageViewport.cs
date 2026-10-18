using Microsoft.UI.Input;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.Foundation;

namespace BookSpineTextRecognition;

public sealed class ImageViewport : Grid
{
    private readonly Canvas _canvas = new();
    private readonly Image _image = new() { Stretch = Stretch.Uniform, IsHitTestVisible = false };
    private readonly ImageViewState _view = new();
    private readonly InputSystemCursor _panCursor = InputSystemCursor.Create(InputSystemCursorShape.SizeAll);
    private BitmapImage? _source;
    private uint? _panPointer;
    private Point _lastPosition;
    public event EventHandler? ViewChanged;
    public event EventHandler? FullscreenRequested;
    public double ZoomFactor => _view.Zoom;
    public double OffsetX => _view.OffsetX;
    public double OffsetY => _view.OffsetY;
    public BitmapImage? Source
    {
        get => _source;
        set { EndPan(); _source = value; _image.Source = value; Fit(); }
    }

    public ImageViewport()
    {
        Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        _canvas.Children.Add(_image); Children.Add(_canvas);
        AutomationProperties.SetName(this, "图片查看器：滚轮缩放，按住鼠标中键自由拖动，双击全屏");
        SizeChanged += (_, _) => Fit();
        AddHandler(PointerPressedEvent, new PointerEventHandler(PointerDown), true);
        AddHandler(PointerMovedEvent, new PointerEventHandler(PointerMove), true);
        AddHandler(PointerReleasedEvent, new PointerEventHandler(PointerUp), true);
        AddHandler(PointerWheelChangedEvent, new PointerEventHandler(PointerWheel), true);
        PointerCaptureLost += (_, _) => EndPan();
        PointerCanceled += (_, _) => EndPan();
        Unloaded += (_, _) => EndPan();
        DoubleTapped += (_, e) => { if (_source is not null) { e.Handled = true; FullscreenRequested?.Invoke(this, EventArgs.Empty); } };
    }

    public void Fit() { _view.Reset(); Render(); }
    public void Zoom(double factor) { if (_source is not null) { _view.ZoomAt(factor, ActualWidth / 2, ActualHeight / 2, ActualWidth, ActualHeight); Render(); } }

    private void PointerDown(object sender, PointerRoutedEventArgs e)
    {
        var point = e.GetCurrentPoint(this);
        if (_source is null || !point.Properties.IsMiddleButtonPressed) return;
        if (CapturePointer(e.Pointer))
        {
            _panPointer = e.Pointer.PointerId; _lastPosition = point.Position; ProtectedCursor = _panCursor;
            e.Handled = true;
        }
    }
    private void PointerMove(object sender, PointerRoutedEventArgs e)
    {
        if (_panPointer != e.Pointer.PointerId) return;
        var point = e.GetCurrentPoint(this);
        if (!point.Properties.IsMiddleButtonPressed) { EndPan(); return; }
        _view.Pan(point.Position.X - _lastPosition.X, point.Position.Y - _lastPosition.Y);
        _lastPosition = point.Position; Render(); e.Handled = true;
    }
    private void PointerUp(object sender, PointerRoutedEventArgs e)
    {
        if (_panPointer != e.Pointer.PointerId) return;
        EndPan(); e.Handled = true;
    }
    private void EndPan()
    {
        var wasPanning = _panPointer.HasValue;
        _panPointer = null; ProtectedCursor = null;
        if (wasPanning) ReleasePointerCaptures();
    }
    private void PointerWheel(object sender, PointerRoutedEventArgs e)
    {
        if (_source is null) return;
        var point = e.GetCurrentPoint(this);
        if (point.Properties.IsHorizontalMouseWheel) return;
        _view.ZoomAt(Math.Pow(1.15, point.Properties.MouseWheelDelta / 120d), point.Position.X, point.Position.Y, ActualWidth, ActualHeight);
        Render(); e.Handled = true;
    }
    private void Render()
    {
        Clip = new RectangleGeometry { Rect = new Rect(0, 0, Math.Max(0, ActualWidth), Math.Max(0, ActualHeight)) };
        if (_source is not null && _source.PixelWidth > 0 && _source.PixelHeight > 0)
        {
            var fit = Math.Min(Math.Max(1, ActualWidth - 24) / _source.PixelWidth, Math.Max(1, ActualHeight - 24) / _source.PixelHeight);
            _image.Width = _source.PixelWidth * fit * _view.Zoom;
            _image.Height = _source.PixelHeight * fit * _view.Zoom;
            Canvas.SetLeft(_image, (ActualWidth - _image.Width) / 2 + _view.OffsetX);
            Canvas.SetTop(_image, (ActualHeight - _image.Height) / 2 + _view.OffsetY);
        }
        ViewChanged?.Invoke(this, EventArgs.Empty);
    }
}
