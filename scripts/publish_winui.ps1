param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$project = Join-Path $projectRoot "desktop\BookSpineTextRecognition\BookSpineTextRecognition.csproj"
$publish = Join-Path $projectRoot "desktop\publish"
$localDotnet = Join-Path $projectRoot "dependencies\dotnet-sdk\dotnet.exe"

if (Test-Path -LiteralPath $localDotnet) {
    $dotnet = $localDotnet
} else {
    $dotnetCommand = Get-Command dotnet -ErrorAction SilentlyContinue
    if ($null -eq $dotnetCommand) {
        throw "未找到 .NET SDK。请运行项目内的安装步骤，或安装 .NET 8 SDK。"
    }
    $dotnet = $dotnetCommand.Source
}

if (-not (Test-Path -LiteralPath $project)) {
    throw "未找到 WinUI 3 项目：$project"
}

if ($Clean -and (Test-Path -LiteralPath $publish)) {
    Remove-Item -LiteralPath $publish -Recurse -Force
}

& $dotnet publish $project `
    -c $Configuration `
    -p:Platform=x64 `
    -r win-x64 `
    --self-contained true `
    -p:WindowsAppSDKSelfContained=true `
    -o $publish

if ($LASTEXITCODE -ne 0) {
    throw "WinUI 3 发布失败，退出代码：$LASTEXITCODE"
}

$executable = Join-Path $publish "BookSpineTextRecognition.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "发布完成但没有找到主程序：$executable"
}

Write-Host "发布完成：$executable"
