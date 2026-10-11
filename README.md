# Book Spine OCR

一个面向书架照片的本地书脊检测与文字识别项目。项目使用 YOLO 实例分割检测每一本书的书脊，再使用 OpenCV 完成裁剪、透视矫正和图像增强，最后通过本地 OCR 识别中文、英文和数字，并输出可复核的 JSON/CSV 结果。

默认流程不依赖大模型：

```text
书架图片
  -> YOLO 书脊实例分割
  -> 掩码裁剪与透视矫正
  -> CLAHE / 灰度增强
  -> PaddleOCR、EasyOCR 或 RapidOCR
  -> 方向候选选择、清洗、排序和低置信度复核队列
```

## 特性

- 本地 YOLO 书脊实例分割，保留每个书脊的多边形和检测框。
- 自动生成掩码裁剪图、原始矩形裁剪图、检测可视化图。
- 对书脊进行旋转矩形透视矫正，并生成彩色、CLAHE 和灰度版本。
- 支持 PaddleOCR CPU、EasyOCR GPU、RapidOCR ONNX GPU 三种本地 OCR 路径。
- OCR 结果支持断点续跑，并输出 JSON、CSV 和人工复核队列。
- 全流程支持命令行批处理、结构化结果输出和本地 FastAPI 服务。

## 数据集

本项目不在仓库中提交完整数据集。数据集来源和下载地址如下：

[wenrenchuyu/book-spine-dataset](https://github.com/wenrenchuyu/book-spine-dataset/tree/main)

下载后按 YOLO 分割数据集结构放置：

```text
dataset/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

类别配置在根目录的 `data.yaml` 中，目前只有一个类别：`spine`。

## 环境要求

- Windows 10/11
- Python 3.10 或 3.11
- NVIDIA GPU 和驱动（训练、EasyOCR GPU、RapidOCR GPU 需要）
- CPU 可以运行数据准备、检测和 PaddleOCR CPU 流程，但训练脚本要求 CUDA

所有依赖默认安装到项目内的 `dependencies/`，不会写入系统 Python 环境。

## 安装依赖

在项目根目录执行：

```powershell
.\scripts\install_dependencies.bat gpu cu130
```

CPU 环境可以执行：

```powershell
.\scripts\install_dependencies.bat cpu
```

激活项目虚拟环境：

```powershell
call .\dependencies\venv\Scripts\activate.bat
```

安装脚本会创建项目内虚拟环境，并安装 Ultralytics、OpenCV、PaddleOCR、PyTorch 和 ONNX Runtime 等基础依赖。EasyOCR 和 RapidOCR ONNX 属于可选 GPU OCR 路径，需要额外安装：

```powershell
.\dependencies\venv\Scripts\python.exe -m pip install easyocr rapidocr_onnxruntime
```

GPU 版 PaddlePaddle 的 Windows/CUDA 支持可能随版本变化；如果自动安装失败，请按本机 CUDA 版本安装官方兼容 wheel。

## 快速运行现有模型

将待识别图片放入 `input/`，并准备训练得到的 YOLO 权重：

```text
outputs/training/book-spine-yolo11n-seg-20261008/weights/best.pt
```

### 1. 检测并裁剪书脊

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\detect_and_crop_spines.py `
  --source .\input `
  --weights .\outputs\training\book-spine-yolo11n-seg-20261008\weights\best.pt `
  --output .\crops\detected `
  --conf 0.35 --iou 0.50 --imgsz 1024 --device 0
```

CPU 检测可将 `--device 0` 改为 `--device cpu`。

输出包括检测可视化图、掩码裁剪图、原始矩形裁剪图和 `detections.json`。

### 2. 透视矫正和图像增强

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\rectify_and_enhance_spines.py `
  --manifest .\crops\detected\detections.json `
  --output .\crops\preprocessed
```

OCR 默认优先使用 `*_clahe.jpg`，灰度图 `*_gray.jpg` 可作为备用输入。

### 3. 本地 PaddleOCR CPU

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\ocr_book_spines.py `
  --input .\crops\preprocessed `
  --output .\outputs\ocr_test `
  --device cpu
```

结果保存为 `ocr_results.json`、`ocr_results.csv` 和 `summary.json`。脚本支持断点续跑；使用 `--overwrite` 可重新处理已有记录。

### 4. 本地 GPU OCR

EasyOCR GPU：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\ocr_book_spines_gpu.py `
  --input .\crops\preprocessed `
  --output .\outputs\ocr_gpu_test
```

RapidOCR ONNX GPU：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\ocr_book_spines_rapid_gpu.py `
  --input .\crops\preprocessed `
  --output .\outputs\ocr_rapid_gpu_test
```

两种 GPU 脚本都会尝试四个方向：原始方向、顺时针 90 度、逆时针 90 度和 180 度，并选择综合置信度最高的结果。

### 5. OCR 后处理

后处理会清洗字符、关联检测坐标、按书架行列排序，并生成低置信度复核队列：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\postprocess_ocr_results.py `
  --ocr .\outputs\ocr_rapid_gpu_test\ocr_results.json `
  --preprocess .\crops\preprocessed\preprocess.json `
  --detections .\crops\detected\detections.json `
  --output .\outputs\ocr_postprocessed
```

主要输出：

| 文件 | 说明 |
| --- | --- |
| `ocr_postprocessed.json` | 全量结构化识别结果 |
| `ocr_postprocessed.csv` | 便于筛选和人工核验的表格 |
| `review_queue.csv` | 空文本、低置信度、方向歧义等待复核记录 |
| `summary.json` | 数量、质量等级和错误统计 |

默认质量等级为：`high >= 0.80`、`medium >= 0.55`、`low < 0.55`。

## 训练和评估

确认数据集已按上文结构放置后，可以先校验数据：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\validate_book_spine_dataset.py
```

训练脚本使用 CUDA 并支持从已有 checkpoint 继续训练：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\train_book_spine.py
```

评估测试集：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\evaluate_book_spine.py
```

当前已保存的测试集评估结果：

| 指标 | 数值 |
| --- | ---: |
| Box Precision | 0.983 |
| Box Recall | 0.982 |
| Box mAP50 | 0.993 |
| Mask Precision | 0.982 |
| Mask Recall | 0.980 |
| Mask mAP50 | 0.992 |
| Mask mAP50-95 | 0.733 |

这些指标来自项目现有测试集运行结果，不代表在其他数据集上的性能保证。

## 项目结构

```text
.
├── config/                         # 配置示例，不保存个人密钥
├── docs/                           # 分步骤实现说明
├── scripts/                        # 数据准备、训练、检测、OCR 和后处理脚本
├── data.yaml                       # YOLO 数据配置
├── app.py                          # 本地 FastAPI 服务
├── README.md
└── .gitignore
```

## 窗口识别程序

运行下面的 WinUI 3 程序可以打开本地窗口。用户可以输入本地图片路径或图片 URL，程序会调用训练好的 YOLO 模型和本地 OCR，在窗口中显示检测图、书脊文字、置信度和识别方向。

```powershell
.\scripts\publish_winui.ps1
.\desktop\publish\BookSpineTextRecognition.exe
```

窗口默认使用 RapidOCR GPU；没有可用 CUDA 时，可以在窗口中选择 PaddleOCR CPU，并将 YOLO 设备填写为 `cpu`。识别过程产生的下载图片、裁剪图、增强图和 JSON 只存放在临时目录，关闭窗口后自动删除，不会写入项目的 `outputs/` 目录。

WinUI 3 的原生运行时不能安全地合并为单个文件，因此发布目录包含主程序 `BookSpineTextRecognition.exe` 和相邻的 Windows App SDK 运行依赖；用户直接启动这个 EXE 即可。模型权重、项目 Python 虚拟环境和脚本仍需保留在项目目录中。

以下目录属于本地运行产物，默认不会提交到 GitHub：`dataset/`、`dependencies/`、`weights/`、`crops/`、`outputs/` 和 `Ultralytics/`。

## 相关文档

- [`docs/book_spine_ocr_implementation.md`](docs/book_spine_ocr_implementation.md)：完整实现流程
- [`docs/dataset_preparation.md`](docs/dataset_preparation.md)：数据准备
- [`docs/model_training.md`](docs/model_training.md)：模型训练
- [`docs/step5_detection_and_cropping.md`](docs/step5_detection_and_cropping.md)：检测和裁剪
- [`docs/step6_7_rectify_enhance.md`](docs/step6_7_rectify_enhance.md)：透视矫正和增强
- [`docs/step9_ocr_postprocess.md`](docs/step9_ocr_postprocess.md)：OCR 后处理
- [`docs/step10_14_completion.md`](docs/step10_14_completion.md)：完整流水线、评估和本地部署
- [`docs/gui_usage.md`](docs/gui_usage.md)：窗口识别程序使用说明
- [`CONTRIBUTING.md`](CONTRIBUTING.md)：远程协作流程

## 远程协作

克隆仓库并创建自己的功能分支：

```powershell
git clone https://github.com/xuwei3378153167-commits/BookSpineTextRecognition.git
cd BookSpineTextRecognition
git switch -c feat/your-change
```

建议每个功能或修复使用独立分支，完成后推送分支并创建 Pull Request：

```powershell
git add README.md scripts docs
git commit -m "feat: describe the change"
git push -u origin feat/your-change
```

不要提交 `dataset/`、`dependencies/`、`weights/`、`crops/`、`outputs/`、凭据或其他本地运行产物。合并前请至少完成相关脚本的本地试跑，并在 Pull Request 中说明运行环境和验证结果。

## 许可证

当前仓库未声明独立许可证。数据集的使用应遵守数据集仓库中的许可证和说明。
