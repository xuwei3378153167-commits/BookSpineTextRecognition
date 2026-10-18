@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
set "PYTHONIOENCODING=utf-8"
"%PROJECT_ROOT%\dependencies\venv\Scripts\python.exe" "%~dp0ocr_paddlevl16.py" %*
exit /b %ERRORLEVEL%
