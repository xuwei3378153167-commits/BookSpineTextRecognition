using System.Diagnostics;
using System.Net.Http.Headers;
using System.Text.Json;

namespace BookSpineTextRecognition;

public sealed class PipelineRunner : IDisposable
{
    private const long MaxImageBytes = 50L * 1024 * 1024;
    private static readonly string[] ImageExtensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"];
    private readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(30) };
    private Process? _runningProcess;

    public async Task<PipelineRunResult> RunAsync(
        string address,
        string ocrEngine,
        string detectDevice,
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        var projectRoot = ProjectPaths.FindRoot();
        var weights = ProjectPaths.FindWeights(projectRoot);
        if (!File.Exists(weights))
        {
            throw new FileNotFoundException("未找到训练好的 YOLO 权重。", weights);
        }

        var temporaryRoot = Path.Combine(Path.GetTempPath(), "BookSpineTextRecognition", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temporaryRoot);

        try
        {
            progress?.Report("正在准备图片……");
            var source = await MaterializeSourceAsync(address, temporaryRoot, cancellationToken);
            var runId = $"winui-{Guid.NewGuid():N}";
            var outputRoot = Path.Combine(temporaryRoot, "runs");
            var script = Path.Combine(projectRoot, "scripts", "run_book_spine_pipeline.py");
            var python = ProjectPaths.FindPython(projectRoot);

            var arguments = new[]
            {
                script,
                "--source", source,
                "--output", outputRoot,
                "--weights", weights,
                "--detect-device", detectDevice,
                "--ocr-engine", ocrEngine,
                "--keep-run-id", runId,
            };

            progress?.Report("正在运行 YOLO 书脊分割和本地 OCR……");
            var output = await RunProcessAsync(python, projectRoot, arguments, progress, cancellationToken);
            var sessionRoot = Path.Combine(outputRoot, runId);
            var resultPath = Path.Combine(sessionRoot, "postprocessed", "books_by_image.json");
            if (!File.Exists(resultPath))
            {
                throw new InvalidOperationException($"推理完成但没有找到结构化结果。\n{output}");
            }

            var structured = JsonSerializer.Deserialize<StructuredResult>(
                await File.ReadAllTextAsync(resultPath, cancellationToken),
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true }) ?? new StructuredResult();
            var annotated = Directory.EnumerateFiles(
                    Path.Combine(sessionRoot, "detected"), "*_detected.*", SearchOption.TopDirectoryOnly)
                .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();

            if (annotated is null)
            {
                throw new InvalidOperationException("推理完成但没有找到检测预览图。");
            }

            progress?.Report($"识别完成，共检测到 {structured.Images.Sum(item => item.Books.Count)} 个书脊。");
            return new PipelineRunResult
            {
                Structured = structured,
                AnnotatedImagePath = annotated,
                TemporaryRoot = temporaryRoot,
            };
        }
        catch
        {
            TryDeleteDirectory(temporaryRoot);
            throw;
        }
    }

    public void Cancel()
    {
        try
        {
            if (_runningProcess is { HasExited: false })
            {
                _runningProcess.Kill(entireProcessTree: true);
            }
        }
        catch (InvalidOperationException)
        {
            // The process can exit between the check and Kill.
        }
        catch (System.ComponentModel.Win32Exception)
        {
            // A child process may already be terminating.
        }
    }

    public void Dispose() => _httpClient.Dispose();

    public static void Cleanup(PipelineRunResult? result)
    {
        if (result is not null)
        {
            TryDeleteDirectory(result.TemporaryRoot);
        }
    }

    private async Task<string> RunProcessAsync(
        string executable,
        string workingDirectory,
        IReadOnlyList<string> arguments,
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = executable,
            WorkingDirectory = workingDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        foreach (var argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        using var process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
        _runningProcess = process;
        try
        {
            if (!process.Start())
            {
                throw new InvalidOperationException("无法启动 Python 推理进程。");
            }

            using var cancelRegistration = cancellationToken.Register(Cancel);
            var standardOutput = process.StandardOutput.ReadToEndAsync();
            var standardError = process.StandardError.ReadToEndAsync();
            // Keep the window alive until all children and output streams close,
            // so cancellation can delete the temporary results reliably.
            await process.WaitForExitAsync();
            var output = await standardOutput;
            var error = await standardError;
            cancellationToken.ThrowIfCancellationRequested();
            if (process.ExitCode != 0)
            {
                throw new InvalidOperationException((error.Length > 0 ? error : output).Trim());
            }

            return output;
        }
        catch (OperationCanceledException)
        {
            Cancel();
            progress?.Report("已取消识别。");
            throw;
        }
        finally
        {
            _runningProcess = null;
        }
    }

    private async Task<string> MaterializeSourceAsync(
        string address,
        string temporaryRoot,
        CancellationToken cancellationToken)
    {
        if (Uri.TryCreate(address, UriKind.Absolute, out var uri) &&
            (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
        {
            using var response = await _httpClient.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            response.EnsureSuccessStatusCode();
            if (response.Content.Headers.ContentLength is > MaxImageBytes)
            {
                throw new InvalidOperationException("图片超过 50 MB，已停止下载。");
            }

            var extension = GetImageExtension(uri, response.Content.Headers.ContentType);
            var destination = Path.Combine(temporaryRoot, $"input{extension}");
            await using var input = await response.Content.ReadAsStreamAsync(cancellationToken);
            await using var file = File.Create(destination);
            var buffer = new byte[81920];
            long total = 0;
            int count;
            while ((count = await input.ReadAsync(buffer, cancellationToken)) > 0)
            {
                total += count;
                if (total > MaxImageBytes) throw new InvalidOperationException("图片超过 50 MB，已停止下载。");
                await file.WriteAsync(buffer.AsMemory(0, count), cancellationToken);
            }
            return destination;
        }

        var localPath = Path.GetFullPath(Environment.ExpandEnvironmentVariables(address));
        if (!File.Exists(localPath))
        {
            throw new FileNotFoundException("找不到图片。", localPath);
        }
        if (new FileInfo(localPath).Length > MaxImageBytes)
            throw new InvalidOperationException("图片超过 50 MB。");

        var localExtension = Path.GetExtension(localPath).ToLowerInvariant();
        if (!ImageExtensions.Contains(localExtension, StringComparer.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("只支持 JPG、PNG、BMP 和 WEBP 图片。");
        }

        var localDestination = Path.Combine(temporaryRoot, $"input{localExtension}");
        File.Copy(localPath, localDestination, overwrite: true);
        return localDestination;
    }

    private static string GetImageExtension(Uri uri, MediaTypeHeaderValue? contentType)
    {
        var uriExtension = Path.GetExtension(uri.AbsolutePath).ToLowerInvariant();
        if (ImageExtensions.Contains(uriExtension, StringComparer.OrdinalIgnoreCase))
        {
            return uriExtension;
        }

        return contentType?.MediaType?.ToLowerInvariant() switch
        {
            "image/jpeg" => ".jpg",
            "image/png" => ".png",
            "image/bmp" => ".bmp",
            "image/webp" => ".webp",
            _ => throw new InvalidOperationException("URL 没有返回支持的图片类型。"),
        };
    }

    private static void TryDeleteDirectory(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
        }
        catch (IOException)
        {
            // A locked preview is harmless; the OS can reclaim the temp directory later.
        }
        catch (UnauthorizedAccessException)
        {
            // A locked preview is harmless; the OS can reclaim the temp directory later.
        }
    }
}
