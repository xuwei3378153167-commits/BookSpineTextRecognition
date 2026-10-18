using Microsoft.UI;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Animation;
using Microsoft.UI.Xaml.Shapes;

namespace BookSpineTextRecognition;

public sealed record PipelineProgress(int Stage, string Message, bool Completed = false);

public sealed class ProgressStepper : Grid
{
    private static readonly string[] Stages = ["图片准备", "书脊检测", "矫正增强", "文字识别", "结果整理"];
    private readonly Border _track, _fill;
    private readonly Ellipse[] _circles = new Ellipse[5], _dots = new Ellipse[5];
    private readonly FontIcon[] _symbols = new FontIcon[5];
    private readonly TextBlock[] _labels = new TextBlock[5];
    private readonly Storyboard _pulse = new();
    private int _completed, _active = -1;
    private bool _paused, _failed;
    public string StateSummary { get; private set; } = "尚未开始";

    public ProgressStepper()
    {
        Visibility = Visibility.Collapsed;
        Height = 62;
        Margin = new Thickness(0, 5, 0, 3);
        var canvas = new Canvas { IsHitTestVisible = false };
        _track = new Border { Height = 6, CornerRadius = new CornerRadius(3), Background = B("#F7F5EF"), BorderBrush = B("#D5CBC0"), BorderThickness = new Thickness(1) };
        _fill = new Border { Height = 6, CornerRadius = new CornerRadius(3), Background = B("#DA7756") };
        canvas.Children.Add(_track); canvas.Children.Add(_fill); Children.Add(canvas);
        var nodes = new Grid();
        for (var i = 0; i < 5; i++)
        {
            nodes.ColumnDefinitions.Add(new ColumnDefinition());
            var cell = new StackPanel { Spacing = 8, HorizontalAlignment = HorizontalAlignment.Center };
            var circle = new Grid { Width = 26, Height = 26 };
            _circles[i] = new Ellipse { StrokeThickness = 1.5 };
            _symbols[i] = new FontIcon { FontSize = 12, HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center };
            _dots[i] = new Ellipse { Width = 7, Height = 7, Fill = B("#DA7756"), HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center };
            circle.Children.Add(_circles[i]); circle.Children.Add(_symbols[i]); circle.Children.Add(_dots[i]);
            _labels[i] = new TextBlock { Text = Stages[i], FontSize = 12, HorizontalAlignment = HorizontalAlignment.Center };
            cell.Children.Add(circle); cell.Children.Add(_labels[i]);
            Grid.SetColumn(cell, i); nodes.Children.Add(cell);
        }
        Children.Add(nodes);
        SizeChanged += (_, _) => DrawTrack();
        Unloaded += (_, _) => _pulse.Stop();
        Loaded += (_, _) => Render();
    }

    public void Start() { _completed = 0; _active = 0; _failed = _paused = false; Visibility = Visibility.Visible; Render(); }
    public void Apply(PipelineProgress progress)
    {
        if (progress.Stage is < 0 or > 4) return;
        _completed = Math.Max(_completed, progress.Completed ? progress.Stage + 1 : progress.Stage);
        _active = progress.Completed ? -1 : progress.Stage;
        Render();
    }
    public void Complete() { _completed = 5; _active = -1; _failed = _paused = false; Render(); }
    public void Stop(bool canceled) { _active = Math.Min(_active < 0 ? _completed : _active, 4); _paused = canceled; _failed = !canceled; Render(); }
    public void Reset() { _pulse.Stop(); _completed = 0; _active = -1; _failed = _paused = false; Visibility = Visibility.Collapsed; }

    private void Render()
    {
        _pulse.Stop(); _pulse.Children.Clear();
        var states = new List<string>();
        for (var i = 0; i < 5; i++)
        {
            var done = i < _completed;
            var active = i == _active && !done;
            var status = done ? "已完成" : active ? _failed ? "失败" : _paused ? "已取消" : "进行中" : "未开始";
            var color = active && _failed ? "#BC3E36" : "#DA7756";
            _circles[i].Fill = B(done ? "#DA7756" : "#F7F5EF");
            _circles[i].Stroke = B(done || active ? color : "#D5CBC0");
            _symbols[i].Glyph = done ? "\uE73E" : _failed ? "\uE711" : "\uE769";
            _symbols[i].Foreground = B(done ? "#FFFFFF" : color);
            _symbols[i].Visibility = done || active && (_failed || _paused) ? Visibility.Visible : Visibility.Collapsed;
            _dots[i].Visibility = active && !_paused && !_failed ? Visibility.Visible : Visibility.Collapsed;
            _dots[i].Opacity = 1;
            _labels[i].Foreground = B(active ? "#A24A2E" : done ? "#312C26" : "#968A7D");
            AutomationProperties.SetName(_labels[i], $"{Stages[i]}：{status}");
            ToolTipService.SetToolTip(_circles[i], status);
            states.Add($"{Stages[i]}：{status}");
            if (active && !_paused && !_failed)
            {
                var animation = new DoubleAnimation { From = 1, To = .2, Duration = new Duration(TimeSpan.FromMilliseconds(650)), AutoReverse = true, RepeatBehavior = RepeatBehavior.Forever, EnableDependentAnimation = true };
                Storyboard.SetTarget(animation, _dots[i]); Storyboard.SetTargetProperty(animation, "Opacity"); _pulse.Children.Add(animation);
            }
        }
        StateSummary = string.Join("；", states);
        AutomationProperties.SetName(this, StateSummary);
        DrawTrack();
        if (IsLoaded && _pulse.Children.Count > 0) _pulse.Begin();
    }

    private void DrawTrack()
    {
        var spacing = ActualWidth / 5;
        Canvas.SetLeft(_track, spacing / 2); Canvas.SetTop(_track, 10);
        Canvas.SetLeft(_fill, spacing / 2); Canvas.SetTop(_fill, 10);
        _track.Width = Math.Max(0, spacing * 4);
        _fill.Width = Math.Max(0, spacing * (_completed - 1));
    }
    private static SolidColorBrush B(string hex) => new(ColorHelper.FromArgb(255, Convert.ToByte(hex[1..3], 16), Convert.ToByte(hex[3..5], 16), Convert.ToByte(hex[5..7], 16)));
}
