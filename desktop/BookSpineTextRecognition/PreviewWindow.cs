using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;

namespace BookSpineTextRecognition;

public sealed class PreviewWindow : Window
{
    private readonly ImageViewport _viewer = new();
    private readonly TextBlock _caption = new() { Foreground = new SolidColorBrush(Colors.White), FontSize = 14, VerticalAlignment = VerticalAlignment.Center, TextTrimming = TextTrimming.CharacterEllipsis };
    private readonly TextBlock _zoom = new() { MinWidth = 52, TextAlignment = TextAlignment.Center, Foreground = new SolidColorBrush(Colors.White), VerticalAlignment = VerticalAlignment.Center };

    public PreviewWindow(BitmapImage image, string caption)
    {
        Title = "图片全屏预览";
        AppWindow.SetIcon(Path.Combine(AppContext.BaseDirectory, "Assets", "BookSpine.ico"));
        var root = new Grid { Background = new SolidColorBrush(ColorHelper.FromArgb(255, 32, 30, 27)), RequestedTheme = ElementTheme.Light };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition());
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var header = new Grid { Padding = new Thickness(24, 12, 24, 8), ColumnSpacing = 20 };
        header.ColumnDefinitions.Add(new ColumnDefinition()); header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.Children.Add(_caption);
        var exit = Button("退出全屏  Esc", (_, _) => Close());
        Grid.SetColumn(exit, 1); header.Children.Add(exit); root.Children.Add(header);
        Grid.SetRow(_viewer, 1); root.Children.Add(_viewer);
        var toolbar = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 12, HorizontalAlignment = HorizontalAlignment.Center, Margin = new Thickness(16) };
        toolbar.Children.Add(Button("−", (_, _) => _viewer.Zoom(.8)));
        toolbar.Children.Add(_zoom);
        toolbar.Children.Add(Button("＋", (_, _) => _viewer.Zoom(1.25)));
        toolbar.Children.Add(Button("适应", (_, _) => _viewer.Fit()));
        Grid.SetRow(toolbar, 2); root.Children.Add(toolbar);
        _viewer.ViewChanged += (_, _) => _zoom.Text = $"{_viewer.ZoomFactor * 100:0}%";
        _viewer.FullscreenRequested += (_, _) => Close();
        var escape = new KeyboardAccelerator { Key = Windows.System.VirtualKey.Escape };
        escape.Invoked += (_, e) => { e.Handled = true; Close(); };
        root.KeyboardAccelerators.Add(escape);
        Content = root;
        SetImage(image, caption);
        AppWindow.SetPresenter(AppWindowPresenterKind.FullScreen);
    }

    public void SetImage(BitmapImage image, string caption) { _caption.Text = caption; _viewer.Source = image; }
    private static Button Button(string text, RoutedEventHandler handler)
    {
        var button = new Button { Content = text, Padding = new Thickness(14, 8, 14, 8) };
        button.Click += handler; return button;
    }
}
