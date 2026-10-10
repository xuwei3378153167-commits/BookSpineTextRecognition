param(
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot "dependencies\venv\Scripts\python.exe"
$script = Join-Path $PSScriptRoot "vlm_review_low_confidence.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到项目 Python 环境：$python"
}

$secureKey = Read-Host "请输入 API Key（输入不显示，且不会写入文件）" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $env:VLM_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $arguments = @($script, "--base-url", $BaseUrl)
    if ($Model) { $arguments += @("--model", $Model) }
    & $python @arguments
    exit $LASTEXITCODE
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    Remove-Item Env:VLM_API_KEY -ErrorAction SilentlyContinue
}
