# WinUI 3 窗口识别程序

先构建发布版本：

```powershell
.\scripts\publish_winui.ps1
```

构建完成后运行：

```powershell
.\desktop\publish\BookSpineTextRecognition.exe
```

在“图片地址”中填写本地图片路径，或者填写 `http://` / `https://` 图片地址。也可以点击“选择图片”打开文件选择器。

WinUI 3 程序使用项目现有的 `run_book_spine_pipeline.py` 完成 YOLO 书脊分割、透视矫正和本地 OCR。结果区域显示每个书脊的文字、置信度、质量等级和方向，左侧显示带检测框的图片。

默认 OCR 引擎是 `rapid-gpu`，需要可用的 ONNX CUDA 环境。CPU 环境请选择 `paddle-cpu`；YOLO 检测设备也应填写为 `cpu`。

项目的 `dependencies\venv` 已包含 PaddleOCR 3.7，并按 GPU 部署保留 PaddlePaddle GPU 包。首次部署或重新创建 GPU 环境时，运行下面的命令安装 CUDA 12.6 依赖：

```powershell
cmd /c .\scripts\install_dependencies.bat gpu cu126
```

PaddleOCR 的模型会在首次初始化时下载并缓存到本机用户目录；模型文件和 Python 依赖不提交到 GitHub。窗口程序会优先调用项目内的 `dependencies\venv\Scripts\python.exe`。

运行 `cmd /c .\scripts\install_dependencies.bat cpu` 时会保留已有的 PaddlePaddle GPU 包；该包也能用于 CPU 推理。只有没有 GPU 包时才安装 CPU 版，避免混装。

2026-10-11 本机已恢复 PaddlePaddle GPU 3.3.1（CUDA 12.6）。窗口的 `paddle-cpu` 选项经真实图片验证可用；脚本 `--device gpu:0` 能运行但识别文字异常，尚不能作为可靠识别结果。窗口暂不提供 PaddleOCR GPU 选项，默认 RapidOCR GPU 不变。

程序不会把输入图片、下载内容、裁剪图、增强图或 OCR JSON 写入项目目录。所有中间文件位于程序创建的临时目录，关闭窗口时自动删除。窗口运行期间也不提供保存结果的按钮。

## 发布说明

WinUI 3 的原生运行时不能安全地合并成单个文件，因此发布目录包含主程序 `BookSpineTextRecognition.exe` 以及相邻的 Windows App SDK 原生依赖；用户直接启动这个 EXE 即可。模型权重、项目 Python 虚拟环境和脚本仍需按项目目录结构保留。
