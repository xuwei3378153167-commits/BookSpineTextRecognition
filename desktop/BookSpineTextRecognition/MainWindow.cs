using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Text;
using Microsoft.UI;
using Microsoft.UI.Text;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.ApplicationModel.DataTransfer;
using Windows.Storage;
using Windows.Storage.Pickers;
using FontWeight = Windows.UI.Text.FontWeight;

namespace BookSpineTextRecognition;

public sealed class MainWindow : Window
{
    private readonly PipelineRunner _runner = new();
    private readonly ObservableCollection<BookResultView> _results = [];
    private readonly SolidColorBrush _ink = Brush("#312C26"), _muted = Brush("#796F65"), _accent = Brush("#DA7756"), _line = Brush("#E8E2D8");
    private readonly Grid _page = new() { RowSpacing = 18, Padding = new Thickness(28, 20, 28, 18) };
    private readonly Grid _workspace = new() { ColumnSpacing = 18, RowSpacing = 18 };
    private readonly Grid _inputGrid = new() { ColumnSpacing = 12, RowSpacing = 12 };
    private readonly TextBox _addressBox = new() { PlaceholderText = "粘贴图片路径或 https:// 图片地址", MinHeight = 42 };
    private readonly ComboBox _engineBox = new() { MinWidth = 172, HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly TextBox _deviceBox = new() { Text = "0", Width = 120 };
    private readonly Button _browseButton, _runButton, _cancelButton, _copyButton, _clearButton;
    private readonly ImageViewport _imageViewer = new();
    private readonly StackPanel _previewEmpty = new() { Spacing = 10, HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center };
    private readonly ListView _resultsList = new() { SelectionMode = ListViewSelectionMode.None, Padding = new Thickness(0) };
    private readonly TextBlock _detectedCount, _recognizedCount, _averageConfidence, _statusText, _stageText, _zoomText, _previewCaption;
    private readonly ProgressStepper _progress = new();
    private readonly ToggleButton _sequenceSort = new() { Content = "顺序 ↑", IsChecked = true, Padding = new Thickness(12, 6, 12, 6) };
    private readonly ToggleButton _confidenceSort = new() { Content = "置信度", Padding = new Thickness(12, 6, 12, 6) };
    private readonly Button _fullscreenButton;
    private bool _sortByConfidence, _sequenceAscending = true, _confidenceAscending;
    private PreviewWindow? _fullscreen;
    private readonly InfoBar _notice = new() { IsOpen = false, IsClosable = true };
    private readonly ToggleButton _originalButton = new() { Content = "原图", IsChecked = true, Padding = new Thickness(12, 6, 12, 6) };
    private readonly ToggleButton _detectedButton = new() { Content = "检测结果", IsEnabled = false, Padding = new Thickness(12, 6, 12, 6) };
    private readonly Border _previewCard, _resultCard;
    private readonly Grid _inputActions;
    private readonly Button _advanced;
    private CancellationTokenSource? _runCancellation;
    private PipelineRunResult? _activeRun;
    private Task? _runTask;
    private bool _closing, _busy;
    private int _previewVersion;
    private string? _originalPath;
    private string? _previewAddress;
    private Task? _previewTask;
    private BitmapImage? _bitmap;

    public MainWindow()
    {
        Title = "本地书脊文字识别";
        AppWindow.SetIcon(Path.Combine(AppContext.BaseDirectory, "Assets", "BookSpine.ico"));
        var bar = AppWindow.TitleBar;
        bar.BackgroundColor = bar.ButtonBackgroundColor = bar.InactiveBackgroundColor = bar.ButtonInactiveBackgroundColor = Color("#F7F5EF");
        bar.ForegroundColor = Color("#312C26");
        bar.ButtonForegroundColor = Color("#796F65");
        _browseButton = Action("选择图片", "\uE8B7", Browse_Click);
        _runButton = Action("开始识别", "\uE768", Run_Click, true);
        _cancelButton = Action("取消", "\uE711", Cancel_Click);
        _cancelButton.Visibility = Visibility.Collapsed;
        _copyButton = Action("复制全部", "\uE8C8", Copy_Click);
        _clearButton = Action("清空", "\uE894", Clear_Click);
        _fullscreenButton = IconButton("\uE740", "全屏预览", (_, _) => OpenFullscreen());
        _fullscreenButton.IsEnabled = false;
        _copyButton.IsEnabled = _clearButton.IsEnabled = false;
        _detectedCount = Text("—", 26, _ink, FontWeights.SemiBold);
        _recognizedCount = Text("—", 26, _ink, FontWeights.SemiBold);
        _averageConfidence = Text("—", 26, _ink, FontWeights.SemiBold);
        _statusText = Text("准备就绪", 13, _ink);
        _stageText = Text("选择或拖入一张书架照片，即可开始", 12, _muted);
        _zoomText = Text("100%", 12, _muted);
        _zoomText.MinWidth = 44;
        _zoomText.TextAlignment = TextAlignment.Center;
        _previewCaption = Text("支持 JPG、PNG、BMP、WEBP · 最大 50 MB", 12, _muted);
        foreach (var (label, tag) in new[] { ("RapidOCR GPU", "rapid-gpu"), ("PaddleOCR GPU", "paddle-gpu"), ("PaddleOCR CPU", "paddle-cpu"), ("PaddleOCR-VL 1.6 GPU", "paddlevl16-gpu") })
            _engineBox.Items.Add(new ComboBoxItem { Content = label, Tag = tag });
        _engineBox.SelectedIndex = 0;
        Name(_addressBox, "图片地址"); Name(_engineBox, "OCR 引擎"); Name(_deviceBox, "YOLO 设备");
        Name(_resultsList, "书脊识别结果");
        AutomationProperties.SetLiveSetting(_statusText, Microsoft.UI.Xaml.Automation.Peers.AutomationLiveSetting.Polite);
        var rowStyle = new Style(typeof(ListViewItem));
        rowStyle.Setters.Add(new Setter(Control.HorizontalContentAlignmentProperty, HorizontalAlignment.Stretch));
        _resultsList.ItemContainerStyle = rowStyle;

        var root = new Grid { Background = Brush("#F7F5EF"), RequestedTheme = ElementTheme.Light };
        var viewport = new ScrollViewer { HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalContentAlignment = HorizontalAlignment.Stretch, Content = _page };
        root.Children.Add(viewport);
        Rows(_page, GridLength.Auto, GridLength.Auto, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        _page.Children.Add(BuildHeader());
        _advanced = BuildAdvanced();
        _inputActions = new Grid { ColumnSpacing = 8 };
        Columns(_inputActions, GridLength.Auto, GridLength.Auto, GridLength.Auto);
        Place(_inputActions, _browseButton, 0, 0); Place(_inputActions, _runButton, 0, 1); Place(_inputActions, _cancelButton, 0, 2);
        Place(_page, BuildInput(), 1);
        _previewCard = BuildPreview(); _resultCard = BuildResults();
        Columns(_workspace, new GridLength(1.12, GridUnitType.Star), new GridLength(1, GridUnitType.Star));
        Rows(_workspace, new GridLength(1, GridUnitType.Star), new GridLength(0));
        Place(_workspace, _previewCard, 0, 0); Place(_workspace, _resultCard, 0, 1);
        Place(_page, _workspace, 2); Place(_page, BuildStatus(), 3);
        viewport.SizeChanged += (_, _) => UpdateLayout(viewport);
        _notice.SizeChanged += (_, _) => UpdateLayout(viewport);
        _progress.SizeChanged += (_, _) => UpdateLayout(viewport);
        Content = root;
        root.AllowDrop = true; root.DragOver += Root_DragOver; root.Drop += Root_Drop;
        _addressBox.LostFocus += async (_, _) => await PreviewAddressAsync();
        _addressBox.KeyDown += async (_, e) => { if (e.Key == Windows.System.VirtualKey.Enter && !_busy) { e.Handled = true; await PreviewAddressAsync(); } };
        _imageViewer.ViewChanged += (_, _) => _zoomText.Text = $"{_imageViewer.ZoomFactor * 100:0}%";
        _imageViewer.FullscreenRequested += (_, _) => OpenFullscreen();
        _sequenceSort.Click += (_, _) => { if (!_sortByConfidence) _sequenceAscending = !_sequenceAscending; _sortByConfidence = false; RefreshResults(); };
        _confidenceSort.Click += (_, _) => { if (_sortByConfidence) _confidenceAscending = !_confidenceAscending; _sortByConfidence = true; RefreshResults(); };
        RefreshSortButtons();
        _originalButton.Click += async (_, _) => await SelectPreviewAsync(false);
        _detectedButton.Click += async (_, _) => await SelectPreviewAsync(true);
        var display = Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(AppWindow.Id, Microsoft.UI.Windowing.DisplayAreaFallback.Primary);
        AppWindow.Resize(new Windows.Graphics.SizeInt32(Math.Min(1680, (int)(display.WorkArea.Width * .86)), Math.Min(1280, (int)(display.WorkArea.Height * .9))));
        Closed += MainWindow_Closed; AppWindow.Closing += AppWindow_Closing;
    }

    private FrameworkElement BuildHeader()
    {
        var grid = new Grid { ColumnSpacing = 12 };
        Columns(grid, GridLength.Auto, new GridLength(1, GridUnitType.Star));
        grid.Children.Add(new Image { Source = new BitmapImage(new Uri(Path.Combine(AppContext.BaseDirectory, "Assets", "BookSpine.png"))), Width = 46, Height = 46 });
        var title = new StackPanel { Spacing = 3, VerticalAlignment = VerticalAlignment.Center };
        title.Children.Add(Text("书脊文字识别", 24, _ink, FontWeights.SemiBold));
        Place(grid, title, 0, 1);
        return grid;
    }

    private FrameworkElement BuildInput()
    {
        var card = Card(); var stack = new StackPanel { Spacing = 12 };
        var heading = new Grid(); Columns(heading, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        heading.Children.Add(Text("导入书架照片", 15, _ink, FontWeights.SemiBold));
        stack.Children.Add(heading);
        Columns(_inputGrid, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        Rows(_inputGrid, GridLength.Auto, GridLength.Auto);
        _inputGrid.Children.Add(_addressBox); Place(_inputGrid, _inputActions, 0, 1); stack.Children.Add(_inputGrid);
        var options = new Grid { ColumnSpacing = 12 };
        Columns(options, GridLength.Auto, GridLength.Auto, new GridLength(1, GridUnitType.Star));
        options.Children.Add(Text("识别引擎", 12, _muted)); Place(options, _engineBox, 0, 1); Place(options, _advanced, 0, 2);
        stack.Children.Add(options); stack.Children.Add(_notice); card.Child = stack;
        return card;
    }

    private Button BuildAdvanced()
    {
        var button = Action("高级设置", "\uE713", (_, _) => { });
        button.HorizontalAlignment = HorizontalAlignment.Right;
        var content = new StackPanel { Spacing = 10, MinWidth = 220 };
        content.Children.Add(Text("检测设备", 16, _ink, FontWeights.SemiBold));
        content.Children.Add(Text("YOLO 书脊分割使用的设备", 12, _muted));
        _deviceBox.HorizontalAlignment = HorizontalAlignment.Left;
        content.Children.Add(_deviceBox);
        content.Children.Add(Text("GPU 填 0；CPU 填 cpu", 12, _muted));
        button.Flyout = new Flyout { Content = content, Placement = FlyoutPlacementMode.BottomEdgeAlignedRight };
        return button;
    }

    private Border BuildPreview()
    {
        var card = Card(); var grid = new Grid { RowSpacing = 12 };
        Rows(grid, GridLength.Auto, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        var heading = new Grid(); Columns(heading, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        heading.Children.Add(Text("图片预览", 17, _ink, FontWeights.SemiBold));
        var tabs = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6 };
        tabs.Children.Add(_originalButton); tabs.Children.Add(_detectedButton); tabs.Children.Add(_fullscreenButton); Place(heading, tabs, 0, 1); grid.Children.Add(heading);
        var surface = new Border { Background = Brush("#F3F0E8"), BorderBrush = _line, BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(10), MinHeight = 180 };
        var surfaceGrid = new Grid(); surfaceGrid.Children.Add(_imageViewer);
        _previewEmpty.Children.Add(new FontIcon { Glyph = "\uEB9F", FontSize = 40, Foreground = _accent, HorizontalAlignment = HorizontalAlignment.Center, Margin = new Thickness(0, 0, 0, 6) });
        _previewEmpty.Children.Add(Text("选择图片后预览", 15, _muted));
        surfaceGrid.Children.Add(_previewEmpty); surface.Child = surfaceGrid; Place(grid, surface, 1);
        var footer = new Grid(); Columns(footer, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        _previewCaption.TextTrimming = TextTrimming.CharacterEllipsis; footer.Children.Add(_previewCaption);
        var zoom = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 4 };
        zoom.Children.Add(IconButton("\uE738", "缩小图片", (_, _) => Zoom(.8f))); zoom.Children.Add(_zoomText);
        zoom.Children.Add(IconButton("\uE710", "放大图片", (_, _) => Zoom(1.25f)));
        var fit = new Button { Content = "适应", Padding = new Thickness(8, 5, 8, 5), Background = Brush("#FFFDF9") };
        fit.Click += (_, _) => FitImage(); ToolTipService.SetToolTip(fit, "将整张图片适应预览区域"); zoom.Children.Add(fit);
        Place(footer, zoom, 0, 1); Place(grid, footer, 2); card.Child = grid;
        return card;
    }

    private Border BuildResults()
    {
        var card = Card(); var grid = new Grid { RowSpacing = 14 };
        Rows(grid, GridLength.Auto, GridLength.Auto, GridLength.Auto, new GridLength(1, GridUnitType.Star));
        var heading = new Grid(); Columns(heading, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        heading.Children.Add(Text("识别结果", 17, _ink, FontWeights.SemiBold));
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6 };
        actions.Children.Add(_copyButton); actions.Children.Add(_clearButton); Place(heading, actions, 0, 1); grid.Children.Add(heading);
        var metrics = new Grid { Background = Brush("#F6F3ED"), CornerRadius = new CornerRadius(10), Padding = new Thickness(16, 12, 16, 12) };
        Columns(metrics, new GridLength(1, GridUnitType.Star), new GridLength(1, GridUnitType.Star), new GridLength(1, GridUnitType.Star));
        Place(metrics, Metric(_detectedCount, "检测书脊"), 0, 0); Place(metrics, Metric(_recognizedCount, "识别文字"), 0, 1); Place(metrics, Metric(_averageConfidence, "平均置信度"), 0, 2); Place(grid, metrics, 1);
        var sorting = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6 };
        sorting.Children.Add(_sequenceSort); sorting.Children.Add(_confidenceSort); Place(grid, sorting, 2);
        Place(grid, _resultsList, 3); card.Child = grid;
        return card;
    }

    private FrameworkElement BuildStatus()
    {
        var stack = new StackPanel { Spacing = 8 }; stack.Children.Add(_progress);
        var grid = new Grid(); Columns(grid, new GridLength(1, GridUnitType.Star));
        var text = new StackPanel { Spacing = 3 }; text.Children.Add(_statusText);
        _stageText.TextWrapping = TextWrapping.Wrap; text.Children.Add(_stageText); grid.Children.Add(text);
        stack.Children.Add(grid);
        return stack;
    }

    private void UpdateLayout(ScrollViewer viewport)
    {
        var compact = viewport.ActualWidth < 1040;
        _page.Padding = new Thickness(compact ? 18 : 28, 18, compact ? 18 : 28, 18);
        _page.Height = Math.Max(viewport.ActualHeight, (compact ? 1120 : 690) + (_progress.Visibility == Visibility.Visible ? 70 : 0) + (_notice.IsOpen ? 85 : 0));
        _workspace.RowSpacing = compact ? 18 : 0;
        _inputGrid.RowSpacing = compact ? 12 : 0;
        _workspace.ColumnDefinitions[0].Width = new GridLength(compact ? 1 : 1.12, GridUnitType.Star);
        _workspace.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
        _workspace.RowDefinitions[1].Height = compact ? new GridLength(1.15, GridUnitType.Star) : new GridLength(0);
        Grid.SetRow(_resultCard, compact ? 1 : 0); Grid.SetColumn(_resultCard, compact ? 0 : 1);
        Grid.SetRow(_inputActions, compact ? 1 : 0); Grid.SetColumn(_inputActions, compact ? 0 : 1);
        Grid.SetColumnSpan(_addressBox, compact ? 2 : 1); Grid.SetColumnSpan(_inputActions, compact ? 2 : 1);
        _inputActions.HorizontalAlignment = compact ? HorizontalAlignment.Left : HorizontalAlignment.Stretch;
    }

    private async void Browse_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var picker = new FileOpenPicker { SuggestedStartLocation = PickerLocationId.PicturesLibrary };
            foreach (var extension in new[] { ".jpg", ".jpeg", ".png", ".bmp", ".webp" }) picker.FileTypeFilter.Add(extension);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, WinRT.Interop.WindowNative.GetWindowHandle(this));
            var file = await picker.PickSingleFileAsync();
            if (file is not null && !_busy) await SetSourceAsync(file.Path);
        }
        catch (Exception ex) { Notice("无法选择图片", ex.Message, InfoBarSeverity.Error); }
    }

    private void Root_DragOver(object sender, DragEventArgs e)
    {
        e.AcceptedOperation = !_busy && e.DataView.Contains(StandardDataFormats.StorageItems) ? DataPackageOperation.Copy : DataPackageOperation.None;
        e.DragUIOverride.Caption = _busy ? "请等待当前任务完成" : "拖入一张书架照片";
        e.DragUIOverride.IsCaptionVisible = true; e.Handled = true;
    }

    private async void Root_Drop(object sender, DragEventArgs e)
    {
        var deferral = e.GetDeferral();
        try
        {
            if (_busy || !e.DataView.Contains(StandardDataFormats.StorageItems)) return;
            var items = await e.DataView.GetStorageItemsAsync();
            if (items.Count != 1 || items[0] is not StorageFile file) { Notice("请拖入一张图片", "每次识别一张照片，请勿拖入文件夹或多个文件。", InfoBarSeverity.Warning); return; }
            await SetSourceAsync(file.Path);
        }
        catch (Exception ex) { Notice("无法导入图片", ex.Message, InfoBarSeverity.Error); }
        finally { deferral.Complete(); }
    }

    private async Task SetSourceAsync(string path)
    {
        if (!new[] { ".jpg", ".jpeg", ".png", ".bmp", ".webp" }.Contains(Path.GetExtension(path).ToLowerInvariant()))
        { Notice("不支持的图片格式", "请选择 JPG、PNG、BMP 或 WEBP 图片。", InfoBarSeverity.Warning); return; }
        _addressBox.Text = path; await PreviewAddressAsync();
    }

    private Task PreviewAddressAsync()
    {
        if (_busy) return Task.CompletedTask;
        var address = _addressBox.Text.Trim().Trim('"');
        if (address == _previewAddress && _previewTask is not null) return _previewTask;
        _previewAddress = address;
        _previewTask = LoadSourceAsync(address);
        return _previewTask;
    }

    private async Task LoadSourceAsync(string address)
    {
        ClearDisplayedResult(); _notice.IsOpen = false; _originalPath = null;
        _bitmap = null; _imageViewer.Source = null; _fullscreenButton.IsEnabled = false; _previewEmpty.Visibility = Visibility.Visible;
        _previewCaption.Text = "支持 JPG、PNG、BMP、WEBP · 最大 50 MB";
        if (string.IsNullOrWhiteSpace(address)) return;
        if (Uri.TryCreate(address, UriKind.Absolute, out var uri) && (uri.Scheme == "http" || uri.Scheme == "https"))
        { SetStatus("图片地址已就绪", "开始识别后下载图片并在本机处理"); return; }
        try
        {
            var path = Path.GetFullPath(Environment.ExpandEnvironmentVariables(address));
            if (!File.Exists(path)) throw new FileNotFoundException("请检查图片路径，文件不存在。", path);
            if (new FileInfo(path).Length > 50L * 1024 * 1024) throw new InvalidOperationException("图片超过 50 MB，请选择较小的图片。");
            await ShowPreviewAsync(path);
            if (_previewAddress == address)
            {
                _originalPath = path;
                SetStatus("图片已就绪", "确认识别引擎后，点击「开始识别」");
            }
        }
        catch (Exception ex) { if (_previewAddress == address) { _originalPath = null; _previewAddress = null; Notice("无法预览图片", ex.Message, InfoBarSeverity.Warning); } }
    }

    private async Task ShowPreviewAsync(string path)
    {
        var version = ++_previewVersion;
        var file = await StorageFile.GetFileFromPathAsync(path);
        using var stream = await file.OpenReadAsync();
        var bitmap = new BitmapImage(); await bitmap.SetSourceAsync(stream);
        if (_closing || version != _previewVersion) return;
        _bitmap = bitmap; _imageViewer.Source = bitmap; _previewEmpty.Visibility = Visibility.Collapsed;
        _fullscreenButton.IsEnabled = true;
        _fullscreen?.SetImage(bitmap, Path.GetFileName(path));
        _previewCaption.Text = Path.GetFileName(path); ToolTipService.SetToolTip(_previewCaption, path); FitImage();
    }

    private async Task SelectPreviewAsync(bool detected)
    {
        _detectedButton.IsChecked = detected; _originalButton.IsChecked = !detected;
        var path = detected ? _activeRun?.AnnotatedImagePath : _originalPath;
        if (path is null) return;
        try { await ShowPreviewAsync(path); } catch (Exception ex) { Notice("预览不可用", ex.Message, InfoBarSeverity.Warning); }
    }

    private void FitImage()
    {
        _imageViewer.Fit();
    }

    private void Zoom(float factor) => _imageViewer.Zoom(factor);

    private void OpenFullscreen()
    {
        if (_bitmap is null) return;
        if (_fullscreen is null)
        {
            var window = new PreviewWindow(_bitmap, _previewCaption.Text);
            _fullscreen = window;
            window.Closed += (_, _) => { if (_fullscreen == window) _fullscreen = null; if (!_closing) Activate(); };
        }
        _fullscreen.Activate();
    }

    private async void Run_Click(object sender, RoutedEventArgs e)
    {
        if (_busy || _runTask is { IsCompleted: false }) return;
        _runTask = RecognizeAsync(); await _runTask;
    }

    private async Task RecognizeAsync()
    {
        var address = _addressBox.Text.Trim().Trim('"');
        if (string.IsNullOrWhiteSpace(address)) { Notice("请先选择图片", "选择本地图片、输入图片地址，或直接拖入一张照片。", InfoBarSeverity.Warning); return; }
        await PreviewAddressAsync();
        var engine = (_engineBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "rapid-gpu";
        var device = string.IsNullOrWhiteSpace(_deviceBox.Text) ? "cpu" : _deviceBox.Text.Trim();
        ClearDisplayedResult(); _notice.IsOpen = false; SetBusy(true);
        _progress.Start();
        SetStatus("正在识别", "正在准备图片…");
        _runCancellation = new CancellationTokenSource(); var timer = Stopwatch.StartNew();
        var progress = new Progress<PipelineProgress>(update =>
        {
            if (!_closing && _busy && _runCancellation is { IsCancellationRequested: false }) { _progress.Apply(update); SetStatus("正在识别", update.Message); }
        });
        try
        {
            if (_originalPath is not null) await ShowPreviewAsync(_originalPath);
            var result = await _runner.RunAsync(address, engine, device, progress, _runCancellation.Token);
            _activeRun = result;
            if (!_closing)
            {
                _originalPath ??= Directory.EnumerateFiles(result.TemporaryRoot, "input.*").FirstOrDefault();
                _previewAddress = address;
                _previewTask = Task.CompletedTask;
                await DisplayResultAsync(result);
                _progress.Complete();
                SetStatus($"识别完成 · {_results.Count} 个书脊", $"用时 {timer.Elapsed.TotalSeconds:0.0} 秒 · 可选择文字或复制全部结果");
            }
        }
        catch (OperationCanceledException)
        {
            _progress.Stop(true);
            SetStatus("已取消识别", "本次临时文件已清理，可重新开始");
        }
        catch (Exception ex)
        {
            _progress.Stop(false);
            SetStatus("识别失败", "请检查图片、模型或设备设置后重试");
            if (!_closing) Notice("识别失败", ex.Message, InfoBarSeverity.Error);
        }
        finally { _runCancellation?.Dispose(); _runCancellation = null; SetBusy(false); }
    }

    private async Task DisplayResultAsync(PipelineRunResult result)
    {
        var books = result.Structured.Images.SelectMany(image => image.Books).ToList();
        foreach (var book in books)
        {
            var view = new BookResultView
            {
                Id = book.Id ?? _results.Count + 1, Text = string.IsNullOrWhiteSpace(book.Text) ? "（未识别）" : book.Text,
                Confidence = book.Confidence?.ToString("0.000") ?? "未提供",
                ConfidenceValue = book.Confidence,
                Quality = book.Quality switch { "high" => "高", "medium" => "中", "low" => "低", "unknown" => "待核验", _ => book.Quality },
                Direction = book.Direction switch { "normal" => "原始", "clockwise" => "顺时针", "counterclockwise" => "逆时针", "180" => "180°", _ => book.Direction },
            };
            _results.Add(view);
        }
        RefreshResults();
        _detectedCount.Text = books.Count.ToString(); _recognizedCount.Text = books.Count(book => !string.IsNullOrWhiteSpace(book.Text)).ToString();
        var scoredBooks = books.Where(book => book.Confidence.HasValue).ToList();
        _averageConfidence.Text = scoredBooks.Count == 0 ? "—" : $"{scoredBooks.Average(book => book.Confidence.GetValueOrDefault()):P0}";
        _detectedButton.IsEnabled = true; _detectedButton.IsChecked = true; _originalButton.IsChecked = false;
        await ShowPreviewAsync(result.AnnotatedImagePath);
        if (books.Count == 0) Notice("没有检测到书脊", "请尝试书脊更清晰、角度更正的照片。", InfoBarSeverity.Informational);
    }

    private IReadOnlyList<BookResultView> SortedResults() => ResultOrdering.Sort(_results, _sortByConfidence, _sortByConfidence ? _confidenceAscending : _sequenceAscending);
    private void RefreshResults()
    {
        _resultsList.Items.Clear();
        foreach (var result in SortedResults()) _resultsList.Items.Add(ResultRow(result));
        RefreshSortButtons();
    }
    private void RefreshSortButtons()
    {
        _sequenceSort.IsChecked = !_sortByConfidence; _confidenceSort.IsChecked = _sortByConfidence;
        _sequenceSort.Content = "顺序" + (!_sortByConfidence ? _sequenceAscending ? " ↑" : " ↓" : "");
        _confidenceSort.Content = "置信度" + (_sortByConfidence ? _confidenceAscending ? " ↑" : " ↓" : "");
        ToolTipService.SetToolTip(_sequenceSort, "按序号排列，再次点击切换升序 / 降序");
        ToolTipService.SetToolTip(_confidenceSort, "按原始置信度排列，再次点击切换升序 / 降序");
        Name(_sequenceSort, "顺序" + (!_sortByConfidence ? _sequenceAscending ? "，升序" : "，降序" : "排序"));
        Name(_confidenceSort, "置信度" + (_sortByConfidence ? _confidenceAscending ? "，升序" : "，降序" : "排序"));
    }

    private FrameworkElement ResultRow(BookResultView book)
    {
        var grid = new Grid { ColumnSpacing = 12, Padding = new Thickness(4, 12, 4, 12), BorderBrush = _line, BorderThickness = new Thickness(0, 0, 0, 1), HorizontalAlignment = HorizontalAlignment.Stretch };
        Columns(grid, GridLength.Auto, new GridLength(1, GridUnitType.Star), GridLength.Auto);
        var number = new Border { Background = Brush("#F4E6DD"), CornerRadius = new CornerRadius(6), MinWidth = 30, Height = 30, Padding = new Thickness(5, 0, 5, 0), VerticalAlignment = VerticalAlignment.Top };
        var id = Text($"{book.Id:00}", 12, Brush("#92513B"), FontWeights.SemiBold); id.HorizontalAlignment = HorizontalAlignment.Center; number.Child = id; grid.Children.Add(number);
        var content = new StackPanel { Spacing = 8 };
        var text = Text(book.Text, 15, _ink, FontWeights.SemiBold); text.TextWrapping = TextWrapping.Wrap; text.IsTextSelectionEnabled = true; content.Children.Add(text);
        var details = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10 };
        var high = book.Quality == "高";
        var quality = new Border { Background = Brush(high ? "#EBF0E5" : book.Quality == "中" ? "#FAEFD7" : "#F9E4DE"), CornerRadius = new CornerRadius(4), Padding = new Thickness(6, 2, 6, 2), Child = Text(book.Quality == "待核验" ? "待核验" : $"{book.Quality}质量", 11, Brush(high ? "#4F6846" : "#92513B")) };
        details.Children.Add(quality); details.Children.Add(Text($"置信度 {book.Confidence}", 11, _muted)); details.Children.Add(Text($"方向 · {book.Direction}", 11, _muted));
        content.Children.Add(details); Place(grid, content, 0, 1);
        var menu = new MenuFlyout(); var copy = new MenuFlyoutItem { Text = "复制此条文字", Icon = new SymbolIcon(Symbol.Copy) };
        copy.Click += (_, _) => CopyText(book.Text, "已复制此条文字"); menu.Items.Add(copy); grid.ContextFlyout = menu;
        text.ContextFlyout = menu;
        var copyButton = IconButton("\uE8C8", $"复制第 {book.Id} 条文字", (_, _) => CopyText(book.Text, "已复制此条文字"));
        copyButton.VerticalAlignment = VerticalAlignment.Top;
        Place(grid, copyButton, 0, 2);
        return grid;
    }

    private void Copy_Click(object sender, RoutedEventArgs e)
    {
        if (_results.Count == 0) return;
        var text = new StringBuilder("序号\t文字\t置信度\t质量\t方向\r\n");
        foreach (var row in SortedResults()) text.AppendLine($"{row.Id}\t{row.Text.Replace('\t', ' ').Replace('\r', ' ').Replace('\n', ' ')}\t{row.Confidence}\t{row.Quality}\t{row.Direction}");
        CopyText(text.ToString(), $"已复制 {_results.Count} 条结果，可粘贴到 Excel 或文本编辑器");
    }

    private void CopyText(string text, string message)
    {
        try { var data = new DataPackage(); data.SetText(text); Clipboard.SetContent(data); Clipboard.Flush(); SetStatus(message, "识别结果仍保留在当前窗口"); }
        catch (Exception ex) { Notice("复制失败", ex.Message, InfoBarSeverity.Warning); }
    }

    private void Cancel_Click(object sender, RoutedEventArgs e)
    {
        _runCancellation?.Cancel(); _runner.Cancel(); _cancelButton.IsEnabled = false;
        SetStatus("正在取消…", "等待推理进程退出并清理临时文件");
    }

    private async void Clear_Click(object sender, RoutedEventArgs e)
    {
        if (_busy) return;
        ClearDisplayedResult(); _notice.IsOpen = false;
        if (_originalPath is not null && File.Exists(_originalPath)) await SelectPreviewAsync(false);
        else { _imageViewer.Source = null; _bitmap = null; _fullscreenButton.IsEnabled = false; _previewEmpty.Visibility = Visibility.Visible; }
        SetStatus("结果已清空", "可继续识别当前图片，或选择新的书架照片");
    }

    private void ClearDisplayedResult()
    {
        ++_previewVersion;
        _progress.Reset();
        _fullscreen?.Close();
        if (_activeRun is not null)
        {
            _imageViewer.Source = null; _bitmap = null; _fullscreenButton.IsEnabled = false;
            if (_originalPath is not null && _originalPath.StartsWith(_activeRun.TemporaryRoot, StringComparison.OrdinalIgnoreCase)) { _originalPath = null; _previewAddress = null; }
        }
        PipelineRunner.Cleanup(_activeRun); _activeRun = null; _results.Clear(); _resultsList.Items.Clear();
        _detectedCount.Text = _recognizedCount.Text = _averageConfidence.Text = "—";
        _detectedButton.IsEnabled = false; _detectedButton.IsChecked = false; _originalButton.IsChecked = true;
        _copyButton.IsEnabled = _clearButton.IsEnabled = false;
    }

    private void SetBusy(bool busy)
    {
        _busy = busy; _runButton.IsEnabled = _browseButton.IsEnabled = _addressBox.IsEnabled = _engineBox.IsEnabled = _advanced.IsEnabled = !busy;
        _cancelButton.Visibility = busy ? Visibility.Visible : Visibility.Collapsed;
        _cancelButton.IsEnabled = busy;
        _copyButton.IsEnabled = !busy && _results.Count > 0; _clearButton.IsEnabled = !busy && _activeRun is not null;
    }

    private void SetStatus(string title, string detail) { _statusText.Text = title; _stageText.Text = detail; }
    private void Notice(string title, string detail, InfoBarSeverity severity)
    {
        _notice.Title = title; _notice.Message = detail.Length > 1200 ? detail[^1200..] : detail; _notice.Severity = severity; _notice.IsOpen = true;
    }

    private void MainWindow_Closed(object sender, WindowEventArgs args)
    {
        _closing = true; ++_previewVersion; _runCancellation?.Cancel(); _runner.Cancel(); _imageViewer.Source = null; _fullscreen?.Close();
        PipelineRunner.Cleanup(_activeRun); _runner.Dispose();
    }

    private async void AppWindow_Closing(Microsoft.UI.Windowing.AppWindow sender, Microsoft.UI.Windowing.AppWindowClosingEventArgs args)
    {
        if (_runTask is { IsCompleted: false })
        {
            args.Cancel = true; if (_closing) return; _closing = true;
            SetStatus("正在关闭", "停止识别并清理临时文件…"); _runCancellation?.Cancel(); _runner.Cancel();
            await _runTask; ClearDisplayedResult(); Close();
        }
    }

    private Border Card() => new() { Background = Brush("#FFFDF9"), BorderBrush = _line, BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(14), Padding = new Thickness(20) };
    private FrameworkElement Metric(TextBlock value, string caption) { var stack = new StackPanel { Spacing = 2 }; stack.Children.Add(value); stack.Children.Add(Text(caption, 11, _muted)); return stack; }
    private Button Action(string text, string glyph, RoutedEventHandler click, bool primary = false)
    {
        var button = new Button { MinHeight = 40, Padding = new Thickness(12, 7, 12, 7), Background = primary ? _accent : Brush("#FFFDF9"), Foreground = _ink, BorderBrush = primary ? _accent : _line, CornerRadius = new CornerRadius(7) };
        var stack = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 7 }; stack.Children.Add(new FontIcon { Glyph = glyph, FontSize = 14 }); stack.Children.Add(Text(text, 13, _ink, primary ? FontWeights.SemiBold : FontWeights.Normal));
        button.Content = stack; button.Click += click; Name(button, text); return button;
    }
    private Button IconButton(string glyph, string label, RoutedEventHandler click)
    {
        var button = new Button { Content = new FontIcon { Glyph = glyph, FontSize = 12 }, Padding = new Thickness(8), Background = Brush("#FFFDF9"), BorderThickness = new Thickness(0) };
        button.Click += click; Name(button, label); ToolTipService.SetToolTip(button, label); return button;
    }
    private static void Name(DependencyObject control, string name) => AutomationProperties.SetName(control, name);
    private static TextBlock Text(string text, double size, Brush brush, FontWeight? weight = null) => new() { Text = text, FontSize = size, Foreground = brush, FontWeight = weight ?? FontWeights.Normal, VerticalAlignment = VerticalAlignment.Center };
    private static Windows.UI.Color Color(string hex) => ColorHelper.FromArgb(255, Convert.ToByte(hex[1..3], 16), Convert.ToByte(hex[3..5], 16), Convert.ToByte(hex[5..7], 16));
    private static SolidColorBrush Brush(string hex) => new(Color(hex));
    private static void Rows(Grid grid, params GridLength[] sizes) { foreach (var size in sizes) grid.RowDefinitions.Add(new RowDefinition { Height = size }); }
    private static void Columns(Grid grid, params GridLength[] sizes) { foreach (var size in sizes) grid.ColumnDefinitions.Add(new ColumnDefinition { Width = size }); }
    private static void Place(Grid grid, FrameworkElement element, int row, int column = 0) { Grid.SetRow(element, row); Grid.SetColumn(element, column); grid.Children.Add(element); }
}
