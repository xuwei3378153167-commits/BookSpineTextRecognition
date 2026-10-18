using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Markup;
using Microsoft.UI.Xaml.XamlTypeInfo;

namespace BookSpineTextRecognition;

public partial class App : Application, IXamlMetadataProvider
{
    private readonly XamlControlsXamlMetaDataProvider _metadata = new();
    public IXamlType GetXamlType(Type type) => _metadata.GetXamlType(type);
    public IXamlType GetXamlType(string name) => _metadata.GetXamlType(name);
    public XmlnsDefinition[] GetXmlnsDefinitions() => _metadata.GetXmlnsDefinitions();
    public static Window? MainWindow { get; private set; }

    public App()
    {
        XamlControlsXamlMetaDataProvider.Initialize();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        // The native Application is fully initialized by this point.
        Resources = new ResourceDictionary();
        Resources.MergedDictionaries.Add(new Microsoft.UI.Xaml.Controls.XamlControlsResources());
        // Native focus, selection and toggle accents share the brand palette.
        var accent = Microsoft.UI.ColorHelper.FromArgb(255, 218, 119, 86);
        Resources["SystemAccentColor"] = accent;
        Resources["SystemAccentColorLight1"] = accent;
        Resources["SystemAccentColorDark1"] = Microsoft.UI.ColorHelper.FromArgb(255, 162, 74, 46);
        Resources["AccentFillColorDefaultBrush"] = new Microsoft.UI.Xaml.Media.SolidColorBrush(accent);
        Resources["AccentFillColorSecondaryBrush"] = new Microsoft.UI.Xaml.Media.SolidColorBrush(accent);
        Resources["SystemControlHighlightAccentBrush"] = new Microsoft.UI.Xaml.Media.SolidColorBrush(accent);
        MainWindow = new MainWindow();
        MainWindow.Activate();
    }
}
