namespace BookSpineTextRecognition;

public static class ProjectPaths
{
    public static string FindRoot()
    {
        var configured = Environment.GetEnvironmentVariable("BOOK_SPINE_PROJECT_ROOT");
        foreach (var candidate in new[] { configured, AppContext.BaseDirectory, Directory.GetCurrentDirectory() })
        {
            if (string.IsNullOrWhiteSpace(candidate))
            {
                continue;
            }

            var current = new DirectoryInfo(Path.GetFullPath(candidate));
            while (current is not null)
            {
                if (File.Exists(Path.Combine(current.FullName, "scripts", "run_book_spine_pipeline.py")))
                {
                    return current.FullName;
                }

                current = current.Parent;
            }
        }

        throw new DirectoryNotFoundException(
            "未找到项目根目录。请将程序放在项目目录或设置 BOOK_SPINE_PROJECT_ROOT 环境变量。");
    }

    public static string FindPython(string root)
    {
        var configured = Environment.GetEnvironmentVariable("BOOK_SPINE_PYTHON");
        if (!string.IsNullOrWhiteSpace(configured)) return configured;
        var projectPython = Path.Combine(root, "dependencies", "venv", "Scripts", "python.exe");
        return File.Exists(projectPython) ? projectPython : "python.exe";
    }

    public static string FindWeights(string root)
    {
        var configured = Environment.GetEnvironmentVariable("BOOK_SPINE_WEIGHTS");
        if (!string.IsNullOrWhiteSpace(configured)) return Path.GetFullPath(configured, root);
        var portableWeights = Path.Combine(root, "weights", "best.pt");
        if (File.Exists(portableWeights)) return portableWeights;
        return Path.Combine(root, "outputs", "training", "book-spine-yolo11n-seg-20261008", "weights", "best.pt");
    }
}
