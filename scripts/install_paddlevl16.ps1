$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'dependencies\venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Install the project GPU environment first.' }
& $pythonPath -m pip install 'transformers==5.20.1' 'accelerate==1.15.0' --index-url https://pypi.org/simple --cache-dir (Join-Path $projectRoot 'dependencies\pip-cache')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$env:HF_HOME = Join-Path $projectRoot 'dependencies\huggingface'
$env:PADDLEVL_MODEL_DIR = Join-Path $projectRoot 'weights\PaddleOCR-VL-1.6'
& $pythonPath -c "import os; from huggingface_hub import snapshot_download; snapshot_download('PaddlePaddle/PaddleOCR-VL-1.6', revision='c5630abae1d940eafe0697512a0325494b02ab42', local_dir=os.environ['PADDLEVL_MODEL_DIR'], ignore_patterns=['.eval_results/*','.gitattributes','model.safetensors'])"
if ($LASTEXITCODE -ne 0) { throw 'Model download failed; rerun to resume.' }
& $pythonPath (Join-Path $PSScriptRoot 'download_paddlevl16_weights.py')
if ($LASTEXITCODE -ne 0) { throw 'Weight download failed; rerun to resume.' }
