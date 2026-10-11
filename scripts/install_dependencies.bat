@echo off
setlocal EnableExtensions

REM Install GPU dependencies for the book spine OCR project.
REM Usage:
REM   install_dependencies.bat              Install GPU dependencies (cu130 default)
REM   install_dependencies.bat gpu cu126    Install CUDA 12.6 wheels
REM   install_dependencies.bat gpu cu118    Install CUDA 11.8 wheels
REM   install_dependencies.bat cpu          Install CPU dependencies explicitly

for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
cd /d "%PROJECT_DIR%"
set "INSTALL_ROOT=%PROJECT_DIR%\dependencies"
set "VENV_DIR=%INSTALL_ROOT%\venv"
set "PIP_CACHE_DIR=%INSTALL_ROOT%\pip-cache"
set "TEMP=%INSTALL_ROOT%\temp"
set "TMP=%INSTALL_ROOT%\temp"
set "MODE=%~1"
set "CUDA_TAG=%~2"

if "%MODE%"=="" set "MODE=gpu"
if "%CUDA_TAG%"=="" set "CUDA_TAG=cu130"
if /I not "%MODE%"=="cpu" if /I not "%MODE%"=="gpu" (
    echo [ERROR] Unknown mode: %MODE%
    echo Usage: %~nx0 [gpu^|cpu] [cu118^|cu124^|cu126^|cu130]
    exit /b 1
)

if /I "%MODE%"=="gpu" if /I not "%CUDA_TAG%"=="cu126" if /I not "%CUDA_TAG%"=="cu118" if /I not "%CUDA_TAG%"=="cu124" if /I not "%CUDA_TAG%"=="cu130" (
    echo [ERROR] Unsupported CUDA wheel tag: %CUDA_TAG%
    echo Supported examples: cu118, cu124, cu126, cu130
    exit /b 1
)

if not exist "%INSTALL_ROOT%" mkdir "%INSTALL_ROOT%"
if errorlevel 1 (
    echo [ERROR] Cannot create installation directory: %INSTALL_ROOT%
    exit /b 1
)
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%"
if not exist "%TEMP%" mkdir "%TEMP%"

echo [INFO] Installation root: %INSTALL_ROOT%
echo [INFO] Virtual environment: %VENV_DIR%
echo [INFO] pip cache: %PIP_CACHE_DIR%

where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
    goto python_found
)

where python >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
    goto python_found
)

echo [ERROR] Python 3 was not found.
echo Install Python 3.10 or 3.11 and enable the PATH option, then run this file again.
exit /b 1

:python_found
echo [INFO] Python command: %PYTHON_CMD%
echo [INFO] Install mode: %MODE%
if /I "%MODE%"=="gpu" echo [INFO] CUDA wheel tag: %CUDA_TAG%

if /I "%MODE%"=="gpu" (
    where nvidia-smi >nul 2>&1
    if errorlevel 1 echo [WARN] nvidia-smi was not found. The GPU packages will install, but runtime use requires an NVIDIA driver.
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] Creating virtual environment: %VENV_DIR%
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        exit /b 1
    )
) else (
    echo [INFO] Reusing existing virtual environment: %VENV_DIR%
)

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

echo [INFO] Upgrading pip, setuptools and wheel...
"%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto install_failed

if /I "%MODE%"=="gpu" goto install_gpu

echo [INFO] Installing CPU PaddlePaddle...
"%VENV_PYTHON%" -m pip show paddlepaddle-gpu >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Keeping the existing GPU wheel; it also supports CPU inference.
    goto install_cpu_torch
)
"%VENV_PYTHON%" -m pip install --index-url https://pypi.org/simple paddlepaddle==3.2.2
if errorlevel 1 goto install_failed
:install_cpu_torch
echo [INFO] Installing CPU PyTorch...
"%VENV_PYTHON%" -m pip install torch torchvision
if errorlevel 1 goto install_failed
goto install_ocr

:install_gpu
echo [INFO] Installing GPU PyTorch (%CUDA_TAG%)...
"%VENV_PYTHON%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/%CUDA_TAG%
if errorlevel 1 goto install_failed

echo [INFO] Installing GPU PaddlePaddle (%CUDA_TAG%)...
REM The GPU wheel is only published on PaddlePaddle's own servers, never on PyPI.
REM Its declared CUDA runtime packages (cu13 for cu130) are resolved from PyPI.
set "PADDLE_VERSION=3.3.1"
set "PADDLE_WHEEL_DIR=%INSTALL_ROOT%\paddle-wheels\%CUDA_TAG%"
if not exist "%PADDLE_WHEEL_DIR%" mkdir "%PADDLE_WHEEL_DIR%"
set "PY_TAG="
"%VENV_PYTHON%" -c "import sys;print('cp{}{}'.format(*sys.version_info[:2]))" > "%TEMP%\paddle_pytag.txt"
set /p PY_TAG=<"%TEMP%\paddle_pytag.txt"
del /q "%TEMP%\paddle_pytag.txt" 2>nul
if "%PY_TAG%"=="" set "PY_TAG=cp313"
set "PADDLE_WHEEL_NAME=paddlepaddle_gpu-%PADDLE_VERSION%-%PY_TAG%-%PY_TAG%-win_amd64.whl"
set "PADDLE_WHEEL_FILE=%PADDLE_WHEEL_DIR%\%PADDLE_WHEEL_NAME%"
REM Download first so a network failure leaves the installed runtime intact.
if exist "%PADDLE_WHEEL_FILE%" (
    echo [INFO] Reusing cached wheel: %PADDLE_WHEEL_FILE%
    goto install_paddle_wheel
)
echo [INFO] Downloading %PADDLE_WHEEL_NAME% from the PaddlePaddle official source...
"%VENV_PYTHON%" -m pip download --no-deps --dest "%PADDLE_WHEEL_DIR%" --index-url https://www.paddlepaddle.org.cn/packages/stable/%CUDA_TAG%/ paddlepaddle-gpu==%PADDLE_VERSION%
if errorlevel 1 (
    echo [WARN] The PaddlePaddle official source is unreachable; falling back to the CDN.
    echo [WARN] This is expected on networks where a mirror proxy blocks the official host.
    del /q "%PADDLE_WHEEL_FILE%" 2>nul
    curl -fL --retry 3 --retry-delay 2 -o "%PADDLE_WHEEL_FILE%" "https://paddle-whl.bj.bcebos.com/stable/%CUDA_TAG%/paddlepaddle-gpu/%PADDLE_WHEEL_NAME%"
    if errorlevel 1 goto install_failed
)
:install_paddle_wheel
if not exist "%PADDLE_WHEEL_FILE%" goto install_failed
REM Both distributions own the paddle directory; never install them together.
"%VENV_PYTHON%" -m pip uninstall -y paddlepaddle
if errorlevel 1 goto install_failed
REM Install the local GPU wheel and let pip resolve its CUDA runtime deps from PyPI.
"%VENV_PYTHON%" -m pip install --find-links "%PADDLE_WHEEL_DIR%" --index-url https://pypi.org/simple paddlepaddle-gpu==%PADDLE_VERSION%
if errorlevel 1 goto install_failed

:install_ocr
echo [INFO] Installing computer vision, OCR and deployment packages...
"%VENV_PYTHON%" -m pip install ultralytics opencv-python numpy pillow pyyaml tqdm rapidfuzz paddleocr==3.7.0 fastapi uvicorn python-multipart onnx
if errorlevel 1 goto install_failed

if /I "%MODE%"=="gpu" (
    echo [INFO] Installing GPU ONNX Runtime...
    "%VENV_PYTHON%" -m pip install onnxruntime-gpu
) else (
    echo [INFO] Installing CPU ONNX Runtime...
    "%VENV_PYTHON%" -m pip install onnxruntime
)
if errorlevel 1 goto install_failed

echo [INFO] Verifying installed packages...
"%VENV_PYTHON%" -c "import sys; sys.path.insert(0, 'scripts'); from ocr_book_spines import configure_paddle_windows_dlls; configure_paddle_windows_dlls(); import paddle; import torch, ultralytics, paddleocr; print('Dependency import verification passed (not an OCR accuracy test)'); print('Torch CUDA:', torch.cuda.is_available()); print('Paddle CUDA build:', paddle.is_compiled_with_cuda())"
if errorlevel 1 goto verify_failed

echo.
echo [OK] Installation completed.
echo [INFO] Virtual environment: %VENV_DIR%
echo [INFO] Activate it with:
echo        call "%VENV_DIR%\Scripts\activate.bat"
echo.
exit /b 0

:install_failed
echo.
echo [ERROR] Dependency installation failed.
echo Check the error above, then run this file again after fixing the issue.
exit /b 1

:verify_failed
echo.
echo [ERROR] Installation finished, but package verification failed.
echo Check the Python and PaddlePaddle installation messages above.
exit /b 1
