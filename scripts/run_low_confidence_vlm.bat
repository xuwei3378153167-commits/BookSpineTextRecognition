@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0.."
set "VLM_BASE_URL="
set "VLM_MODEL="
set /p "VLM_BASE_URL=请输入 OpenAI 兼容 Base URL（例如 https://api.example.com/v1）："
if "%VLM_BASE_URL%"=="" (
  echo 未提供 Base URL，已取消。
  exit /b 1
)
set /p "VLM_MODEL=请输入视觉模型名（直接回车将自动从 /models 选择）："
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_low_confidence_vlm.ps1" -BaseUrl "%VLM_BASE_URL%" -Model "%VLM_MODEL%"
exit /b %ERRORLEVEL%
