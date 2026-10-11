using System.Collections.ObjectModel;
using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Microsoft.UI.Xaml.Shapes;
using Windows.Storage;
using Windows.Storage.Pickers;
using Microsoft.UI.Text;
using FontWeight = Windows.UI.Text.FontWeight;

namespace BookSpineTextRecognition;

public sealed class MainWindow : Window
{
    private readonly PipelineRunner _runner = new();
    private readonly ObservableCollection<BookResultView> _results = [];
    private readonly SolidColorBrush _inkBrush = Brush("#18313A");
    private readonly SolidColorBrush _mutedBrush = Brush("#6A7F86");
    private readonly SolidColorBrush _accentBrush = Brush("#087F7A");
    private readonly SolidColorBrush _lineBrush = Brush("#DCE7E8");
    private readonly TextBox _addressBox;
    private readonly ComboBox _engineBox;
    private readonly TextBox _deviceBox;
    private readonly Button _browseButton;
    private readonly Button _runButton;
    private readonly Button _cancelButton;
    private readonly Image _previewImage;
    private readonly StackPanel _previewEmptyState;
    private readonly StackPanel _resultsPanel;
    private readonly TextBlock _detectedCount;
    private readonly TextBlock _recognizedCount;
    private readonly TextBlock _averageConfidence;
    private readonly ProgressRing _progress;
    private readonly TextBlock _statusText;
    private CancellationTokenSource? _runCancellation;
    private PipelineRunResult? _activeRun;
    private Task? _runTask;
    private bool _closing;

    public MainWindow()
    {
        Title = "本地书脊文字识别";
        _addressBox = new TextBox { Height = 42, PlaceholderText = "输入本地路径，或粘贴 http:// / https:// 图片地址" };
        _engineBox = new ComboBox { Width = 168, SelectedIndex = 0 };
        _engineBox.Items.Add(new ComboBoxItem { Content = "RapidOCR GPU", Tag = "rapid-gpu" });
        _engineBox.Items.Add(new ComboBoxItem { Content = "PaddleOCR GPU", Tag = "paddle-gpu" });
        _engineBox.Items.Add(new ComboBoxItem { Content = "PaddleOCR CPU", Tag = "paddle-cpu" });
        _engineBox.SelectedIndex = 0;
        _deviceBox = new TextBox { Text = "0", Width = 70, Height = 34 };
        _browseButton = ActionButton("选择图片", "\uE8B7", BrowseButton_Click);
        _runButton = ActionButton("开始识别", "\uE768", RunButton_Click, _accentBrush, new SolidColorBrush(Colors.White));
        _cancelButton = ActionButton("取消", "\uE711", CancelButton_Click);
        _cancelButton.IsEnabled = false;
        _previewImage = new Image { Stretch = Stretch.Uniform, Visibility = Visibility.Collapsed };
        _previewEmptyState = EmptyPreview();
        _resultsPanel = new StackPanel { Spacing = 0 };
        _detectedCount = MetricValue("0");
        _recognizedCount = MetricValue("0");
        _averageConfidence = MetricValue("0.000");
        _progress = new ProgressRing { Width = 18, Height = 18, IsActive = false, Foreground = _accentBrush };
        _statusText = new TextBlock { Text = "准备就绪", Foreground = _inkBrush, FontSize = 13, VerticalAlignment = VerticalAlignment.Center };

        Content = BuildPage();
        var display = Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(AppWindow.Id, Microsoft.UI.Windowing.DisplayAreaFallback.Primary);
        AppWindow.Resize(new Windows.Graphics.SizeInt32(
            Math.Min(2000, (int)(display.WorkArea.Width * .9)),
            Math.Min(1280, (int)(display.WorkArea.Height * .9))));
        Closed += MainWindow_Closed;
        AppWindow.Closing += AppWindow_Closing;
    }

    private UIElement BuildPage()
    {
        var root = new Grid { Background = Brush("#F4F7F8"), RequestedTheme = ElementTheme.Light };
        AddRows(root, GridLength.Auto, GridLength.Auto, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        root.Children.Add(BuildHeader());
        var input = BuildInputCard();
        Grid.SetRow(input, 1);
        root.Children.Add(input);
        var content = BuildContentArea();
        Grid.SetRow(content, 2);
        root.Children.Add(content);
        var status = BuildStatusBar();
        Grid.SetRow(status, 3);
        root.Children.Add(status);
        return root;
    }

    private FrameworkElement BuildHeader()
    {
        var header = new Border { Background = Brush("#12343D"), Padding = new Thickness(32, 26, 32, 24) };
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition());
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var title = new StackPanel { Spacing = 5 };
        title.Children.Add(new TextBlock { Text = "BOOK SPINE OCR", Foreground = Brush("#8FE0D5"), FontSize = 12, FontWeight = FontWeights.SemiBold, CharacterSpacing = 90 });
        title.Children.Add(new TextBlock { Text = "本地书脊文字识别", Foreground = new SolidColorBrush(Colors.White), FontSize = 30, FontWeight = FontWeights.SemiBold });
        title.Children.Add(new TextBlock { Text = "分割、矫正、识别，一次完成。结果只在本次运行期间保留。", Foreground = Brush("#C5D9DC"), FontSize = 14 });
        grid.Children.Add(title);
        var badge = new Border { Background = Brush("#1E4A52"), CornerRadius = new CornerRadius(8), Padding = new Thickness(16, 11, 16, 11), VerticalAlignment = VerticalAlignment.Center };
        var badgeContent = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 9 };
        badgeContent.Children.Add(new Ellipse { Width = 9, Height = 9, Fill = Brush("#66D7A7"), VerticalAlignment = VerticalAlignment.Center });
        badgeContent.Children.Add(new TextBlock { Text = "本地推理", Foreground = Brush("#E6FFFA"), FontSize = 13 });
        badge.Child = badgeContent;
        Grid.SetColumn(badge, 1);
        grid.Children.Add(badge);
        header.Child = grid;
        return header;
    }

    private FrameworkElement BuildInputCard()
    {
        var card = Card(new Thickness(28, 22, 28, 16), new Thickness(20));
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition());
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var address = new StackPanel { Spacing = 8 };
        address.Children.Add(Label("图片地址", _inkBrush, 14, FontWeights.SemiBold));
        address.Children.Add(_addressBox);
        grid.Children.Add(address);
        var options = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10, Margin = new Thickness(0, 14, 0, 0) };
        options.Children.Add(Label("OCR 引擎", _mutedBrush));
        options.Children.Add(_engineBox);
        options.Children.Add(Label("YOLO 设备", _mutedBrush, 13, FontWeights.Normal, new Thickness(12, 0, 0, 0)));
        options.Children.Add(_deviceBox);
        options.Children.Add(Label("GPU 填 0；CPU 填 cpu", _mutedBrush, 12));
        Grid.SetRow(options, 1);
        grid.Children.Add(options);
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(22, 0, 0, 0) };
        actions.Children.Add(_browseButton);
        actions.Children.Add(_runButton);
        actions.Children.Add(_cancelButton);
        Grid.SetColumn(actions, 1);
        Grid.SetRowSpan(actions, 2);
        grid.Children.Add(actions);
        card.Child = grid;
        return card;
    }

    private FrameworkElement BuildContentArea()
    {
        var area = new Grid { Margin = new Thickness(28, 0, 28, 18), ColumnSpacing = 16 };
        area.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1.05, GridUnitType.Star) });
        area.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        var previewCard = Card(new Thickness(0), new Thickness(18));
        var previewGrid = new Grid();
        AddRows(previewGrid, GridLength.Auto, new GridLength(1, GridUnitType.Star));
        previewGrid.Children.Add(SectionHeading("检测预览", "YOLO 分割结果", "实时预览"));
        var previewSurface = new Grid { Background = Brush("#F7FAFA") };
        previewSurface.Children.Add(_previewImage);
        previewSurface.Children.Add(_previewEmptyState);
        Grid.SetRow(previewSurface, 1);
        previewGrid.Children.Add(previewSurface);
        previewCard.Child = previewGrid;
        area.Children.Add(previewCard);

        var resultCard = Card(new Thickness(0), new Thickness(18));
        var resultGrid = new Grid();
        AddRows(resultGrid, GridLength.Auto, GridLength.Auto, new GridLength(1, GridUnitType.Star));
        resultGrid.Children.Add(ResultHeading());
        var metrics = new Grid { Margin = new Thickness(0, 16, 0, 14) };
        metrics.ColumnDefinitions.Add(new ColumnDefinition());
        metrics.ColumnDefinitions.Add(new ColumnDefinition());
        metrics.ColumnDefinitions.Add(new ColumnDefinition());
        metrics.Children.Add(Metric(_detectedCount, "书脊"));
        var recognized = Metric(_recognizedCount, "有文字");
        Grid.SetColumn(recognized, 1);
        metrics.Children.Add(recognized);
        var confidence = Metric(_averageConfidence, "平均置信度");
        Grid.SetColumn(confidence, 2);
        metrics.Children.Add(confidence);
        Grid.SetRow(metrics, 1);
        resultGrid.Children.Add(metrics);
        var resultsScroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto, BorderBrush = _lineBrush, BorderThickness = new Thickness(1), Background = Brush("#FBFCFC") };
        var resultStack = new StackPanel();
        resultStack.Children.Add(ResultHeader());
        resultStack.Children.Add(_resultsPanel);
        resultsScroll.Content = resultStack;
        Grid.SetRow(resultsScroll, 2);
        resultGrid.Children.Add(resultsScroll);
        resultCard.Child = resultGrid;
        Grid.SetColumn(resultCard, 1);
        area.Children.Add(resultCard);
        return area;
    }

    private FrameworkElement BuildStatusBar()
    {
        var bar = new Border { Margin = new Thickness(28, 0, 28, 18), Padding = new Thickness(12, 9, 12, 9), Background = Brush("#EAF3F2"), CornerRadius = new CornerRadius(6) };
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition());
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.Children.Add(_progress);
        _statusText.Margin = new Thickness(10, 0, 0, 0);
        Grid.SetColumn(_statusText, 1);
        grid.Children.Add(_statusText);
        var note = new TextBlock { Text = "临时结果 · 关闭程序后自动清理", Foreground = _mutedBrush, FontSize = 12, VerticalAlignment = VerticalAlignment.Center };
        Grid.SetColumn(note, 2);
        grid.Children.Add(note);
        bar.Child = grid;
        return bar;
    }

    private FrameworkElement ResultHeading()
    {
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition());
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var stack = new StackPanel { Spacing = 3 };
        stack.Children.Add(Label("识别结果", _inkBrush, 18, FontWeights.SemiBold));
        stack.Children.Add(Label("按书架阅读顺序排列", _mutedBrush, 12));
        grid.Children.Add(stack);
        var clear = new Button { Content = "清空", Padding = new Thickness(11, 6, 11, 6), Background = new SolidColorBrush(Colors.Transparent), BorderBrush = _lineBrush, BorderThickness = new Thickness(1) };
        clear.Click += ClearButton_Click;
        Grid.SetColumn(clear, 1);
        grid.Children.Add(clear);
        return grid;
    }

    private FrameworkElement ResultHeader()
    {
        var grid = TableGrid("#", "文字", "置信度", "质量", "方向", Brush("#EFF5F5"));
        grid.Padding = new Thickness(12, 9, 12, 9);
        return grid;
    }

    private FrameworkElement SectionHeading(string title, string subtitle, string badgeText)
    {
        var grid = new Grid { Margin = new Thickness(0, 0, 0, 12) };
        grid.ColumnDefinitions.Add(new ColumnDefinition());
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var stack = new StackPanel { Spacing = 3 };
        stack.Children.Add(Label(title, _inkBrush, 18, FontWeights.SemiBold));
        stack.Children.Add(Label(subtitle, _mutedBrush, 12));
        grid.Children.Add(stack);
        var badge = new Border { Background = Brush("#E3F3F1"), CornerRadius = new CornerRadius(6), Padding = new Thickness(10, 5, 10, 5) };
        badge.Child = Label(badgeText, _accentBrush, 12);
        Grid.SetColumn(badge, 1);
        grid.Children.Add(badge);
        return grid;
    }

    private StackPanel EmptyPreview()
    {
        var empty = new StackPanel { HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center, Spacing = 9 };
        empty.Children.Add(new FontIcon { Glyph = "\uE91B", FontSize = 40, Foreground = Brush("#A5B9BC"), HorizontalAlignment = HorizontalAlignment.Center });
        empty.Children.Add(Label("等待图片", _mutedBrush, 16));
        empty.Children.Add(Label("输入图片地址后开始本地识别", Brush("#91A5A9"), 12));
        return empty;
    }

    private Button ActionButton(string text, string glyph, RoutedEventHandler handler, Brush? background = null, Brush? foreground = null)
    {
        var button = new Button { Height = 42, Padding = new Thickness(16, 0, 16, 0) };
        if (background is not null) button.Background = background;
        if (foreground is not null) button.Foreground = foreground;
        var content = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        content.Children.Add(new FontIcon { Glyph = glyph, FontSize = 15 });
        content.Children.Add(new TextBlock { Text = text });
        button.Content = content;
        button.Click += handler;
        return button;
    }

    private static TextBlock MetricValue(string value) => new() { Text = value, FontSize = 22, FontWeight = FontWeights.SemiBold };

    private FrameworkElement Metric(TextBlock value, string caption)
    {
        var stack = new StackPanel { Spacing = 2 };
        value.Foreground = _accentBrush;
        stack.Children.Add(value);
        stack.Children.Add(Label(caption, _mutedBrush, 12));
        return stack;
    }

    private Grid TableGrid(string id, string text, string confidence, string quality, string direction, Brush background)
    {
        var grid = new Grid { Background = background };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(42) });
        grid.ColumnDefinitions.Add(new ColumnDefinition());
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(72) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(58) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(92) });
        AddCell(grid, id, 0, _mutedBrush, 12);
        AddCell(grid, text, 1, _inkBrush, 13);
        AddCell(grid, confidence, 2, _inkBrush, 13);
        AddCell(grid, quality, 3, _inkBrush, 13);
        AddCell(grid, direction, 4, _mutedBrush, 13);
        return grid;
    }

    private void AddResult(BookResultView book)
    {
        var row = TableGrid(book.Id.ToString(), book.Text, book.Confidence, book.Quality, book.Direction, new SolidColorBrush(Colors.Transparent));
        row.Padding = new Thickness(12, 10, 12, 10);
        _resultsPanel.Children.Add(row);
    }

    private static void AddCell(Grid grid, string text, int column, Brush foreground, double size)
    {
        var cell = new TextBlock { Text = text, Foreground = foreground, FontSize = size, TextWrapping = TextWrapping.Wrap, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) };
        ToolTipService.SetToolTip(cell, text);
        Grid.SetColumn(cell, column);
        grid.Children.Add(cell);
    }

    private static Border Card(Thickness margin, Thickness padding) => new() { Margin = margin, Padding = padding, Background = Brush("#FFFFFF"), BorderBrush = Brush("#DCE7E8"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(8) };

    private static TextBlock Label(string text, Brush foreground, double size = 14, FontWeight? weight = null, Thickness? margin = null) => new() { Text = text, Foreground = foreground, FontSize = size, FontWeight = weight ?? FontWeights.Normal, Margin = margin ?? new Thickness(0), VerticalAlignment = VerticalAlignment.Center };

    private static SolidColorBrush Brush(string hex) => new(ColorHelper.FromArgb(255, Convert.ToByte(hex[1..3], 16), Convert.ToByte(hex[3..5], 16), Convert.ToByte(hex[5..7], 16)));

    private static void AddRows(Grid grid, params GridLength[] heights)
    {
        foreach (var height in heights) grid.RowDefinitions.Add(new RowDefinition { Height = height });
    }

    private async void BrowseButton_Click(object sender, RoutedEventArgs e)
    {
        var picker = new FileOpenPicker { SuggestedStartLocation = PickerLocationId.PicturesLibrary };
        foreach (var extension in new[] { ".jpg", ".jpeg", ".png", ".bmp", ".webp" }) picker.FileTypeFilter.Add(extension);
        var windowHandle = WinRT.Interop.WindowNative.GetWindowHandle(this);
        WinRT.Interop.InitializeWithWindow.Initialize(picker, windowHandle);
        var file = await picker.PickSingleFileAsync();
        if (file is not null) _addressBox.Text = file.Path;
    }

    private async void RunButton_Click(object sender, RoutedEventArgs e)
    {
        _runTask = RecognizeAsync();
        await _runTask;
    }

    private async Task RecognizeAsync()
    {
        var address = _addressBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(address))
        {
            await ShowMessageAsync("还没有图片", "请先输入图片路径或图片 URL。", "知道了");
            return;
        }

        var engine = (_engineBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "rapid-gpu";
        var device = string.IsNullOrWhiteSpace(_deviceBox.Text) ? "cpu" : _deviceBox.Text.Trim();
        SetBusy(true);
        ClearDisplayedResult();
        _runCancellation = new CancellationTokenSource();
        var progress = new Progress<string>(message => { if (!_closing) _statusText.Text = message; });
        try
        {
            var result = await _runner.RunAsync(address, engine, device, progress, _runCancellation.Token);
            _activeRun = result;
            if (!_closing) await DisplayResultAsync(result);
        }
        catch (OperationCanceledException)
        {
            _statusText.Text = "已取消识别";
        }
        catch (Exception ex)
        {
            _statusText.Text = "识别失败";
            if (!_closing) await ShowMessageAsync("识别失败", ex.Message, "关闭");
        }
        finally
        {
            _runCancellation?.Dispose();
            _runCancellation = null;
            SetBusy(false);
        }
    }

    private void CancelButton_Click(object sender, RoutedEventArgs e)
    {
        _runCancellation?.Cancel();
        _runner.Cancel();
        _statusText.Text = "正在取消……";
    }

    private void ClearButton_Click(object sender, RoutedEventArgs e)
    {
        ClearDisplayedResult();
        _statusText.Text = "准备就绪";
    }

    private async Task DisplayResultAsync(PipelineRunResult result)
    {
        _results.Clear();
        _resultsPanel.Children.Clear();
        var books = result.Structured.Images.SelectMany(image => image.Books).ToList();
        foreach (var book in books)
        {
            var view = new BookResultView
            {
                Id = book.Id ?? _results.Count + 1,
                Text = string.IsNullOrWhiteSpace(book.Text) ? "（未识别）" : book.Text,
                Confidence = book.Confidence.ToString("0.000"),
                Quality = book.Quality switch { "high" => "高", "medium" => "中", "low" => "低", _ => book.Quality },
                Direction = book.Direction switch { "normal" => "原始", "clockwise" => "顺时针", "counterclockwise" => "逆时针", "180" => "180°", _ => book.Direction },
            };
            _results.Add(view);
            AddResult(view);
        }
        _detectedCount.Text = books.Count.ToString();
        _recognizedCount.Text = books.Count(book => !string.IsNullOrWhiteSpace(book.Text)).ToString();
        _averageConfidence.Text = books.Count == 0 ? "0.000" : books.Average(book => book.Confidence).ToString("0.000");
        var bitmap = new BitmapImage { DecodePixelWidth = 1400 };
        var imageFile = await StorageFile.GetFileFromPathAsync(result.AnnotatedImagePath);
        using var stream = await imageFile.OpenReadAsync();
        await bitmap.SetSourceAsync(stream);
        _previewImage.Source = bitmap;
        _previewImage.Visibility = Visibility.Visible;
        _previewEmptyState.Visibility = Visibility.Collapsed;
        _statusText.Text = $"识别完成 · 检测到 {books.Count} 个书脊";
    }

    private void ClearDisplayedResult()
    {
        _previewImage.Source = null;
        PipelineRunner.Cleanup(_activeRun);
        _activeRun = null;
        _results.Clear();
        _resultsPanel.Children.Clear();
        _previewImage.Visibility = Visibility.Collapsed;
        _previewEmptyState.Visibility = Visibility.Visible;
        _detectedCount.Text = "0";
        _recognizedCount.Text = "0";
        _averageConfidence.Text = "0.000";
    }

    private void SetBusy(bool busy)
    {
        _runButton.IsEnabled = !busy;
        _browseButton.IsEnabled = !busy;
        _cancelButton.IsEnabled = busy;
        _progress.IsActive = busy;
        _addressBox.IsEnabled = !busy;
        _engineBox.IsEnabled = !busy;
        _deviceBox.IsEnabled = !busy;
    }

    private async Task ShowMessageAsync(string title, string content, string closeText)
    {
        var root = Content as FrameworkElement;
        var dialog = new ContentDialog { Title = title, Content = content, CloseButtonText = closeText, XamlRoot = root?.XamlRoot };
        await dialog.ShowAsync();
    }

    private void MainWindow_Closed(object sender, WindowEventArgs args)
    {
        _runCancellation?.Cancel();
        _runner.Cancel();
        PipelineRunner.Cleanup(_activeRun);
        _activeRun = null;
        _runner.Dispose();
    }

    private async void AppWindow_Closing(Microsoft.UI.Windowing.AppWindow sender, Microsoft.UI.Windowing.AppWindowClosingEventArgs args)
    {
        if (_runTask is { IsCompleted: false })
        {
            args.Cancel = true;
            if (_closing) return;
            _closing = true;
            _statusText.Text = "正在停止识别并清理临时结果……";
            _runCancellation?.Cancel();
            _runner.Cancel();
            await _runTask;
            ClearDisplayedResult();
            Close();
        }
    }
}
