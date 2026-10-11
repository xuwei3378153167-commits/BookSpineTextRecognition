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
"%VENV_PYTHON%" -m pip install --index-url https://pypi.org/simple paddlepaddle==3.2.2
if errorlevel 1 goto install_failed
echo [INFO] Installing CPU PyTorch...
"%VENV_PYTHON%" -m pip install torch torchvision
if errorlevel 1 goto install_failed
goto install_ocr

:install_gpu
echo [INFO] Installing GPU PyTorch (%CUDA_TAG%)...
"%VENV_PYTHON%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/%CUDA_TAG%
if errorlevel 1 goto install_failed

echo [INFO] Installing GPU PaddlePaddle (%CUDA_TAG%)...
echo [WARN] If PaddlePaddle has no matching Windows wheel, install its official wheel for your CUDA version manually.
"%VENV_PYTHON%" -m pip install paddlepaddle-gpu --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/%CUDA_TAG%/
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
"%VENV_PYTHON%" -c "import cv2, numpy, torch, ultralytics, paddle, paddleocr; print('Dependency verification passed'); print('Torch CUDA:', torch.cuda.is_available()); print('Paddle device:', paddle.device.get_device())"
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
