# BookSpineTextRecognition 项目交接文档

更新时间：2026-10-11  
当前分支：`main`  
当前提交：以 `git log -1` 为准
远程仓库：[xuwei3378153167-commits/BookSpineTextRecognition](https://github.com/xuwei3378153167-commits/BookSpineTextRecognition)

## 1. 项目目标

这是一个书脊检测、透视矫正和文字识别项目。输入一张书架或书籍图片后，流程会：

1. 使用 YOLO 模型检测或分割书脊。
2. 对书脊进行裁剪、透视矫正和图像增强。
3. 使用本地 OCR 引擎识别书脊文字。
4. 通过 WinUI 3 窗口展示检测图和识别结果。

数据集不上传到仓库，README 中使用外部数据集链接：

<https://github.com/wenrenchuyu/book-spine-dataset/tree/main>

## 2. 当前已完成内容

- 已完成 Python 书脊处理和 OCR 流程。
- 已完成 WinUI 3 桌面窗口程序。
- 用户可以输入本地图片路径或图片 URL，也可以通过文件选择器选择图片。
- 窗口关闭时清理临时图片、裁剪图、增强图和 OCR 结果，不保存用户输出。
- 已集成 RapidOCR GPU 和 PaddleOCR（CPU 与 GPU）。
- 已保留 PaddlePaddle GPU 运行时，并修复 Blackwell 上的 GPU 识别异常。
- 已排除第三方大模型 OCR、数据集、模型权重、虚拟环境和生成结果。
- README、GUI 使用说明和依赖安装脚本已同步到 GitHub。

## 3. 重要目录

| 路径 | 用途 | 是否提交 Git |
|---|---|---|
| `scripts/` | Python 推理、OCR、安装和 WinUI 发布脚本 | 是 |
| `desktop/BookSpineTextRecognition/` | WinUI 3 源代码 | 是 |
| `docs/gui_usage.md` | GUI 使用说明 | 是 |
| `README.md` | 项目总说明 | 是 |
| `data.yaml` | YOLO 数据配置 | 是 |
| `dataset/` | 本地数据集 | 否 |
| `weights/` | YOLO 和 OCR 模型权重 | 否 |
| `dependencies/` | Python 虚拟环境、缓存和临时文件 | 否 |
| `crops/` | 裁剪及预处理图片 | 否 |
| `outputs/` | OCR 输出和其他运行结果 | 否 |
| `Ultralytics/` | 本地运行依赖或模型相关目录 | 否 |

不要把被 `.gitignore` 忽略的本地目录强行加入仓库。

## 4. 本机已验证环境

当前项目位于：`D:\Documents\机器学习`

- Windows
- NVIDIA GeForce RTX 5060
- NVIDIA 驱动：591.86
- 驱动报告 CUDA：13.1
- 项目虚拟环境：`dependencies\venv`
- PaddleOCR：3.7.0
- PaddlePaddle GPU：3.3.1（`cu130` wheel，CUDA 13.0 运行库，cuDNN 9.13）
- PaddleOCR 模型缓存位于用户目录下的 `.paddlex\official_models`

验证过的 GPU 包状态：

```powershell
dependencies\venv\Scripts\python.exe -m pip show paddlepaddle-gpu
```

### GPU 识别异常已修复（2026-10-11）

本机 RTX 5060 Laptop 为 Blackwell 架构（计算能力 sm_120）。此前安装的 `paddlepaddle-gpu==3.3.1` 是 `cu126`（CUDA 12.6）构建，在 Blackwell 上内核不匹配：GPU 数据拷贝正常、卷积和矩阵乘法正确，但所有逐元素算子（`ones`、加法、乘法、ReLU、`sum`、`softmax`）恒返回 0 且不报错，`paddle.utils.run_check()` 反而能通过。这不是硬件或驱动问题，同一张卡上的 PyTorch `2.14.1+cu130`（arch_list 含 sm_120）完全正常。

改用 `cu130` 版 wheel（CUDA 13.0、cuDNN 9.13.0）后逐元素算子、矩阵运算和真实书脊 OCR 全部恢复正常。40 张书脊图 GPU 与 CPU 文字 38/40 完全一致，其余 2 张仅字符顺序轻微差异（数值精度差异，非乱码）；GPU 约 10.09 秒，CPU 约 469.64 秒，约 46 倍加速。样例“名人名言录 H03319 王涵等编”GPU 置信度约 0.986，与 CPU 一致。

因此 GUI 默认仍为 `rapid-gpu`，`PaddleOCR GPU` 与 `PaddleOCR CPU` 选项均已恢复并可用。不能仅凭 GPU 初始化成功或高置信度判断识别正确；排查 GPU 问题时应先跑逐元素算子对照（例如 `paddle.ones([4])` 是否全为 1）。

## 5. 依赖安装

默认 GPU 安装：

```powershell
cmd /c .\scripts\install_dependencies.bat gpu cu130
```

也支持 `cu118`、`cu124`、`cu126` 和 `cu130`；对 Blackwell（RTX 50 系）应使用 `cu130`。用户本机配置了清华 PyPI 镜像，但 PaddlePaddle GPU wheel 只托管在 PaddlePaddle 官方服务器，PyPI 上不存在。安装脚本会先尝试官方源 `https://www.paddlepaddle.org.cn/packages/stable/<tag>/`，失败时自动回退到官方 CDN `https://paddle-whl.bj.bcebos.com/stable/<tag>/paddlepaddle-gpu/`，再从 PyPI 解析 wheel 声明的 CUDA 运行库依赖。

本机网络下 `www.paddlepaddle.org.cn` 的 TLS 握手会失败（DNS 解析到代理假 IP），而 `paddle-whl.bj.bcebos.com` 可正常访问。下载失败时优先改用官方 CDN，不要只重复清华镜像。

CPU 兼容安装：

```powershell
cmd /c .\scripts\install_dependencies.bat cpu
```

安装脚本会保留已有的 `paddlepaddle-gpu`，因为 CPU 推理也可以使用 GPU 包。CPU 和 GPU 包不能同时覆盖同一个 `paddle` 目录。

## 6. 主要运行方式

批量 PaddleOCR CPU 测试：

```powershell
dependencies\venv\Scripts\python.exe scripts\ocr_book_spines.py `
  --device cpu `
  --input crops\preprocessed_test `
  --output outputs\ocr_test
```

PaddleOCR GPU 探测命令，仅用于后续质量排查：

```powershell
dependencies\venv\Scripts\python.exe scripts\ocr_book_spines.py `
  --device gpu:0 `
  --max-images 1 `
  --output dependencies\temp\paddleocr_gpu_smoke `
  --overwrite
```

RapidOCR、YOLO 和窗口程序的具体用法见 `README.md` 与 `docs/gui_usage.md`。

PaddleOCR GPU 识别（已验证可用）：

```powershell
dependencies\venv\Scripts\python.exe scripts\ocr_book_spines.py `
  --device gpu:0 `
  --input crops\preprocessed_test `
  --output dependencies\temp\paddleocr_gpu_test `
  --overwrite
```

构建并运行 WinUI 3：

```powershell
.\scripts\publish_winui.ps1
.\desktop\publish\BookSpineTextRecognition.exe
```

## 7. 关键代码注意事项

### `scripts/ocr_book_spines.py`

- `configure_paddle_windows_dlls()` 必须在导入 `paddleocr` 前执行。
- Windows 下需要加入项目虚拟环境中的 `paddle\libs`、`torch\lib` 和 NVIDIA DLL 目录（`site-packages\nvidia\*\bin`）。
- Paddle GPU wheel 即使执行 CPU 推理，也必须先导入 Paddle 并设置设备，否则可能出现 `cudnn_cnn64_9.dll` 的 `WinError 127`。
- `enable_mkldnn=False` 是当前 GPU wheel 在 CPU 推理时避免 oneDNN PIR 属性错误所必需的兼容设置。
- 结果文件应保持可恢复写入，但输出目录必须位于本地忽略目录或 GUI 临时目录。
- `cu130` wheel 使用 `site-packages\nvidia\cu13\bin\x86_64` 下的 CUDA 13 DLL（`cudart64_13`、`cublas64_13` 等），由 Paddle 自身加载；`cu126` 则使用 `nvidia\*\bin` 下的 CUDA 12 DLL。两套 nvidia 包可以并存。

### `scripts/install_dependencies.bat`

- GPU 分支先用 `pip download` 尝试 PaddlePaddle 官方源，失败时用 `curl` 回退到 bcebos CDN。
- wheel 下载到 `dependencies\paddle-wheels\<tag>\` 后，用 `pip install --find-links <dir> --index-url https://pypi.org/simple paddlepaddle-gpu==3.3.1` 一次装好 wheel 及其 CUDA 运行库依赖；不要用 `--no-deps`，否则 cu13 运行库不会安装。
- 安装 GPU wheel 前必须先卸载 `paddlepaddle`（CPU 包），两者不能同时覆盖同一个 `paddle` 目录。

### WinUI 3

- GUI 优先调用 `dependencies\venv\Scripts\python.exe`。
- GUI 传入的是本地临时目录，程序退出时清理。
- 发布目录不能只保留一个 EXE；Windows App SDK 原生运行库必须与 EXE 一起保留。

## 8. 安全和提交边界

禁止提交以下内容：

- 数据集图片和标注。
- `best.pt` 等模型权重。
- `dependencies/venv`、pip 缓存和 PaddleX 模型缓存。
- OCR JSON、裁剪图片、增强图片和批处理结果。
- 第三方大模型 OCR 的 API 密钥、请求内容和返回结果。
- `config/*.env`、`.env` 或其他凭据。

提交前检查：

```powershell
git status --short
git diff --check
git ls-files dataset weights dependencies crops outputs Ultralytics
```

最后一条命令应没有输出。

## 9. 已知问题和推荐下一步

1. ~~**PaddleOCR GPU 文字质量异常**~~：已修复。根因是 `cu126` wheel 在 Blackwell（sm_120）上内核不匹配，改用 `cu130` wheel 后 GPU 识别正常。若后续在其他机器复现同类异常，先跑逐元素算子对照（`paddle.ones([4])` 是否全为 1）定位，再检查 CUDA/cuDNN 组合与 wheel 的 CUDA 标签是否匹配 GPU 架构。
2. **GPU 安装脚本需持续关注官方 wheel 可用性**：不同 CUDA 标签和 Python 版本的官方 Windows wheel 可能不同；`cu124` 当前在 bcebos CDN 上不存在。下载阶段失败时不能卸载现有 PaddlePaddle 包。下载失败时优先切换官方 CDN。
3. ~~**GUI 只开放 PaddleOCR CPU**~~：已恢复。WinUI 引擎列表现提供 `rapid-gpu`、`paddle-gpu`、`paddle-cpu`；`paddle-gpu` 会自动以 `gpu:0` 运行 OCR。
4. **不要重新训练模型**：已有训练权重和预处理裁剪图应优先复用，除非后续任务明确要求重新训练。
5. **继续同步 GitHub**：完成代码修改后提交到 `main`，并确认本地 HEAD 与 `origin/main` 一致。
6. **GPU 环境体积较大**：`cu130` wheel 约 509 MB，加上 CUDA 13 运行库依赖（cuDNN 约 339 MB、cuBLAS 约 402 MB 等）会显著增大本地 `dependencies\`；这些目录已被 `.gitignore` 忽略，不要提交。

## 10. 最近提交记录

```text
运行 git log --oneline -6 查看最新提交
```

截至本文档更新时，`main` 分支上的近期提交包括：PaddlePaddle GPU 修复（cu130 wheel）、WinUI 引擎选项恢复，以及文档同步。

后续模型接手时，先读取本文件、`README.md`、`docs/gui_usage.md` 和当前 Git 状态，再进行修改。
