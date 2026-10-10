# 书脊图片文字识别实现步骤

本文档给出一套完全本地化的书脊图片文字识别方案。系统使用 YOLO 分割每本书的书脊，再使用 OpenCV 完成裁剪、透视矫正和图像增强，最后使用 PaddleOCR 在本地识别中文、英文和数字。

整体流程如下：

```text
环境与依赖安装
    ↓
采集并标注书脊数据
    ↓
训练 YOLO 书脊分割模型
    ↓
检测书脊并生成独立裁剪图
    ↓
透视矫正、旋转和图像增强
    ↓
本地 OCR 识别
    ↓
文字清洗、排序和置信度处理
    ↓
结果验证与本地部署
```

## 第一步：安装所有依赖

### 1.1 Windows 一键安装

当前项目的 `scripts` 目录中提供 `install\\\_dependencies.bat`。脚本默认安装 GPU 版本依赖，并将虚拟环境、所有 Python 包、pip 缓存和临时文件统一放在项目内的 `dependencies` 文件夹。由于项目位于 D 盘，这些依赖仍然全部安装在 D 盘。双击运行或在 PowerShell 中执行：

```powershell
.\\\\scripts\\\\install\\\_dependencies.bat
```

脚本默认使用 CUDA 13.0（`cu130`）安装 GPU 版 PyTorch；其他 GPU 依赖根据其 Windows wheel 支持情况单独安装。RTX 5060（计算能力 sm_120）需要包含 sm_120 内核的 PyTorch 构建。

* 创建 `dependencies\\\\venv` 虚拟环境；
* 升级 `pip`、`setuptools` 和 `wheel`；
* 安装 YOLO、OpenCV、NumPy 等基础依赖；
* 安装 GPU 版 PyTorch、PaddlePaddle 和 ONNX Runtime；
* 安装 PaddleOCR、FastAPI 等依赖；
* 执行导入检查。

如果本机 CUDA 版本对应其他 wheel 标签，可以传入标签，例如 CUDA 11.8：

```powershell
.\\\\install\\\_dependencies.bat gpu cu118
```

PyTorch 支持的示例标签包括 `cu118`、`cu124`、`cu126` 和 `cu130`。标签也会用于脚本尝试安装的 GPU PaddlePaddle wheel；若 PaddlePaddle 尚无对应 Windows wheel，请按其官方 Windows 支持情况单独选择。

安装完成后，激活虚拟环境：

```powershell
call dependencies\\\\venv\\\\Scripts\\\\activate.bat
```

如需明确安装 CPU 依赖，可执行：

```powershell
.\\\\scripts\\\\install\\\_dependencies.bat cpu
```

### 1.2 安装 Python

建议使用 Python 3.10 或 Python 3.11，并确认命令行可以正常执行：

```bash
python --version
```

批处理脚本会自动在 D 盘创建虚拟环境，因此不需要手动执行 `python -m venv`。如果只想手动安装，可自行创建虚拟环境，但后续命令必须在该虚拟环境中执行。

### 1.3 手动安装基础依赖（可选）

```bash
python -m pip install --upgrade pip
pip install ultralytics opencv-python numpy pillow pyyaml tqdm
```

### 1.4 手动安装 OCR 依赖（可选）

CPU 环境：

```bash
pip install paddlepaddle paddleocr
```

GPU 环境需要按照本机 CUDA 版本安装对应的 PaddlePaddle GPU 包，然后安装 OCR。使用本文提供的批处理脚本时，这一步已经自动完成：

```bash
pip install paddleocr
```

PaddlePaddle 的 GPU 安装命令应以官方安装页面与本机 CUDA 版本为准。安装完成后检查：

```bash
python -c "import paddle; print(paddle.\\\_\\\_version\\\_\\\_); print(paddle.device.get\\\_device())"
```

### 1.5 手动安装可选依赖（可选）

用于本地书名词典模糊匹配：

```bash
pip install rapidfuzz
```

用于 API 部署：

```bash
pip install fastapi uvicorn python-multipart
```

用于 CPU ONNX 推理：

```bash
pip install onnx onnxruntime
```

GPU 环境应使用 `onnxruntime-gpu`，批处理脚本会自动安装该版本。

### 1.6 验证安装

```bash
python -c "from ultralytics import YOLO; import cv2; from paddleocr import PaddleOCR; print('依赖安装成功')"
```

如果这一步失败，应先解决 Python、CUDA、PaddlePaddle 或模型下载问题，再继续后面的步骤。

## 第二步：准备项目目录

建议建立以下目录：

```text
book\\\_spine\\\_ocr/
├── docs/
│   └── book\\\_spine\\\_ocr\\\_implementation.md
├── scripts/
│   └── install\\\_dependencies.bat
├── dependencies/
│   ├── venv/
│   ├── pip-cache/
│   └── temp/
├── dataset/
│   ├── images/
│   │   ├── train/
│   │   ├── val/
│   │   └── test/
│   └── labels/
│       ├── train/
│       ├── val/
│       └── test/
├── crops/
├── outputs/
├── weights/
└── data.yaml
```

批处理文件位于 `scripts`，说明文档位于 `docs`，Python 虚拟环境及其安装包位于 `dependencies`。图片放入 `dataset/images`，YOLO 标签放入对应的 `dataset/labels` 目录。建议将数据按 8:1:1 划分为训练集、验证集和测试集。

## 第三步：采集并标注书脊图片

图片应覆盖以下情况：

* 中文、英文、数字混合；
* 横排、竖排和倾斜书脊；
* 光照、阴影、反光和模糊；
* 书脊密集排列、部分遮挡和不同宽度；
* 不同拍摄距离、角度和背景。

建议先准备 500 至 2000 张真实业务图片。图片数量少时，应优先保证场景多样性。

使用 CVAT、Labelme 等工具进行多边形标注。第一版只设置一个类别：

```text
spine
```

每一本书的书脊都必须作为一个独立实例标注，尽量沿书脊边缘绘制多边形。不要把相邻书脊合并成一个区域，否则会影响后续裁剪和 OCR。

创建 `data.yaml`：

```yaml
path: D:/book\\\_spine\\\_ocr/dataset
train: images/train
val: images/val
test: images/test

names:
  0: spine
```

## 第四步：训练 YOLO 书脊分割模型

推荐从 YOLO11s-seg 开始训练。书脊通常比较细长，训练时应使用较大的输入尺寸。

```bash
yolo segment train \\\\
  model=yolo11s-seg.pt \\\\
  data=data.yaml \\\\
  epochs=150 \\\\
  imgsz=1280 \\\\
  batch=4 \\\\
  device=0 \\\\
  workers=4 \\\\
  patience=30 \\\\
  project=runs/book\\\_spine \\\\
  name=yolo\\\_spine\\\_seg
```

Windows PowerShell 可以写成一行：

```powershell
yolo segment train model=yolo11s-seg.pt data=data.yaml epochs=150 imgsz=1280 batch=4 device=0 workers=4 patience=30 project=runs/book\\\_spine name=yolo\\\_spine\\\_seg
```

模型选择建议：

|模型|适用情况|
|-|-|
|`yolo11n-seg`|CPU 或低延迟场景|
|`yolo11s-seg`|推荐的速度与精度平衡方案|
|`yolo11m-seg`|书脊密集、遮挡较多|
|`yolo11l-seg`|对分割精度要求高且显存充足|

训练完成后，重点检查：

* `mask mAP50`；
* 书脊召回率；
* 细窄书脊漏检情况；
* 相邻书脊是否被粘连；
* 遮挡和反光场景下的表现。

将最佳权重复制或记录为：

```text
runs/book\\\_spine/yolo\\\_spine\\\_seg/weights/best.pt
```

## 第五步：检测书脊并生成裁剪图

项目已提供可直接运行的 `scripts/detect_and_crop_spines.py`。它使用训练得到的 `best.pt`，按分割掩码生成白底书脊裁剪图，并同时保存原始矩形裁剪、检测可视化和 `detections.json` 坐标清单。默认给掩码外扩 4%，避免切掉书脊边缘。

处理单张图片：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\detect_and_crop_spines.py `
  --source .\input\shelf_001.jpg `
  --output .\crops\shelf_001
```

处理一个目录：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\detect_and_crop_spines.py `
  --source .\input `
  --output .\crops\detected `
  --conf 0.35 --iou 0.50 --imgsz 1024
```

每张输入图会生成一张 `_detected.jpg`；每个书脊目录中保存 `spine_001.jpg`（掩码外区域置白）和 `spine_001_raw.jpg`（矩形原图裁剪）。后续透视矫正和 OCR 使用前者，排查误检时查看后者。

使用 YOLO 推理时应保留分割掩码：

```python
from ultralytics import YOLO
import cv2

model = YOLO("runs/book\\\_spine/yolo\\\_spine\\\_seg/weights/best.pt")
image = cv2.imread("input.jpg")

result = model.predict(
    source=image,
    conf=0.35,
    iou=0.5,
    imgsz=1280,
    retina\\\_masks=True,
    verbose=False,
)\\\[0]
```

不要只使用矩形检测框裁剪，因为矩形框可能包含相邻书本或书架背景。应优先使用分割掩码，并从掩码轮廓计算最小外接矩形或四边形。

## 第六步：透视矫正与方向处理

项目脚本 `scripts/rectify_and_enhance_spines.py` 已实现这一步。它读取第五步的 `detections.json` 和多边形坐标，使用最小外接旋转矩形进行透视矫正；如果结果横向，则自动旋转为竖直书脊。

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\rectify_and_enhance_spines.py `
  --manifest .\crops\detected\detections.json `
  --output .\crops\preprocessed
```

每个实例会保存 `_rectified.jpg`，并在后续增强步骤生成 `_clahe.jpg` 和 `_gray.jpg`。处理参数、局部四角坐标、输出尺寸和失败记录保存在 `preprocess.json`。

书脊可能因为拍摄角度产生倾斜，需要先进行透视矫正，再交给 OCR。

```python
import cv2
import numpy as np

def order\\\_points(points):
    points = np.asarray(points, dtype=np.float32)
    result = np.zeros((4, 2), dtype=np.float32)
    total = points.sum(axis=1)
    diff = np.diff(points, axis=1).reshape(-1)
    result\\\[0] = points\\\[np.argmin(total)]
    result\\\[2] = points\\\[np.argmax(total)]
    result\\\[1] = points\\\[np.argmin(diff)]
    result\\\[3] = points\\\[np.argmax(diff)]
    return result

def perspective\\\_crop(image, corners):
    corners = order\\\_points(corners)
    width = int(max(
        np.linalg.norm(corners\\\[2] - corners\\\[3]),
        np.linalg.norm(corners\\\[1] - corners\\\[0]),
    ))
    height = int(max(
        np.linalg.norm(corners\\\[1] - corners\\\[2]),
        np.linalg.norm(corners\\\[0] - corners\\\[3]),
    ))

    target = np.array(\\\[
        \\\[0, 0],
        \\\[width - 1, 0],
        \\\[width - 1, height - 1],
        \\\[0, height - 1],
    ], dtype=np.float32)

    matrix = cv2.getPerspectiveTransform(corners, target)
    return cv2.warpPerspective(image, matrix, (width, height))
```

书脊文字方向不确定时，可以分别对原图、顺时针 90 度、逆时针 90 度和 180 度图像进行 OCR，最后选择置信度最高的结果。

## 第七步：图像增强

脚本默认对矫正图按高度放大到约 1600 像素，并在 LAB 空间的亮度通道应用 CLAHE；同时保留灰度版本。彩色 CLAHE 图优先作为 OCR 输入，灰度图用于低对比度或需要二次阈值化的样本。

本次测试集已完成：`crops/preprocessed_test/` 下有 1,278 个实例，分别生成 1,278 张矫正图、1,278 张 CLAHE 图和 1,278 张灰度图，`preprocess.json` 中记录 0 个失败。

书脊裁剪图应至少生成一份放大和对比度增强版本：

```python
def preprocess(image):
    image = cv2.resize(
        image, None, fx=2, fy=2,
        interpolation=cv2.INTER\\\_CUBIC,
    )

    lab = cv2.cvtColor(image, cv2.COLOR\\\_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    image = cv2.merge(\\\[l, a, b])
    return cv2.cvtColor(image, cv2.COLOR\\\_LAB2BGR)
```

低质量图片可以额外尝试灰度化、锐化和自适应二值化。实际项目中建议保留多个预处理版本，分别识别后选择综合置信度最高的结果。

## 第八步：使用本地 OCR 识别文字

初始化 PaddleOCR：

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    lang="ch",
    use\\\_doc\\\_orientation\\\_classify=False,
    use\\\_doc\\\_unwarping=False,
    use\\\_textline\\\_orientation=True,
)
```

不同版本的 PaddleOCR 参数和返回结构可能不同，应以本机安装版本的示例为准。

基本识别逻辑：

```python
def recognize\\\_candidates(ocr, crop):
    images = \\\[
        ("normal", crop),
        ("clockwise", cv2.rotate(crop, cv2.ROTATE\\\_90\\\_CLOCKWISE)),
        ("counterclockwise", cv2.rotate(crop, cv2.ROTATE\\\_90\\\_COUNTERCLOCKWISE)),
        ("180", cv2.rotate(crop, cv2.ROTATE\\\_180)),
    ]

    candidates = \\\[]
    for direction, image in images:
        image = preprocess(image)
        result = ocr.predict(image)
        # 根据本机 PaddleOCR 版本提取 rec\\\_texts 和 rec\\\_scores
        candidates.append({
            "direction": direction,
            "raw\\\_result": result,
        })

    return candidates
```

建议保存 OCR 原始结果，便于调试和调整后处理规则。

## 第九步：清洗、排序和过滤 OCR 结果

基础文本清洗：

```python
import re

def clean\\\_text(text):
    text = text.replace(" ", "").replace("\\\\\\\\n", "")
    text = text.replace("|", "一")
    return re.sub(
        r"\\\[^\\\\\\\\u4e00-\\\\\\\\u9fffA-Za-z0-9，。！？：、（）《》“”‘’\\\\\\\\-·]",
        "",
        text,
    )
```

建议设置结果等级：

```text
high：confidence >= 0.80
medium：0.55 <= confidence < 0.80
low：confidence < 0.55
```

低置信度结果应保留裁剪图并标记为待复核，不宜直接作为最终书名。

YOLO 返回的目标顺序不固定，应根据书脊中心点排序。单行书架按 `center\\\_x` 排序，多行书架先按 `center\\\_y` 聚类，再按 `center\\\_x` 排序。

如果有本地图书目录，可以使用 `rapidfuzz` 对 OCR 文本进行模糊匹配，用于修正漏字、错字和近似书名。该过程仍然完全在本地运行。

## 第十步：保存结构化结果

第九步的可执行实现见 [OCR 结果后处理](step9_ocr_postprocess.md)。先运行后处理脚本，再使用其 `ocr_postprocessed.json` 或 `ocr_postprocessed.csv` 作为第十步的结构化结果输入。

推荐输出 JSON：

```json
{
  "image": "shelf\\\_001.jpg",
  "books": \\\[
    {
      "id": 1,
      "text": "机器学习",
      "confidence": 0.94,
      "direction": "clockwise",
      "bbox": \\\[120, 80, 185, 620],
      "polygon": \\\[\\\[120, 80], \\\[185, 90], \\\[180, 620], \\\[115, 610]],
      "crop\\\_path": "crops/shelf\\\_001\\\_001.jpg"
    }
  ]
}
```

裁剪图片单独保存到 `crops/`，JSON 中只保存图片路径，不要直接写入图片对象。

## 第十一步：建立完整推理脚本

第十步至第十四步的可执行实现和验收命令见 [后续步骤完成说明](step10_14_completion.md)。完整流水线入口为 `scripts/run_book_spine_pipeline.py`，评估入口为 `scripts/evaluate_pipeline.py`。

完整脚本至少应包含以下模块：

```text
load\\\_models()       加载 YOLO 和 OCR 模型
detect\\\_spines()     检测并取得书脊掩码
crop\\\_spine()        轮廓提取和透视裁剪
preprocess()        放大、增强和旋转
recognize\\\_text()    OCR 识别
clean\\\_text()        文本清洗
sort\\\_books()        书脊排序
save\\\_result()       保存裁剪图和 JSON
```

建议先实现单张图片推理，再扩展到批量目录处理。批量处理时应记录失败图片、平均置信度和耗时。

## 第十二步：测试与评估

测试集应包含训练时没有出现过的图片。重点统计：

* 书脊检测召回率；
* 分割 `mask mAP50`；
* OCR 完全正确率；
* 书名字符准确率；
* 低置信度比例；
* 单张图片平均处理时间。

建议建立一个人工核验表：

```text
图片名 | 书脊数量是否正确 | 书名是否正确 | OCR 置信度 | 是否需要复核
```

测试时要单独统计窄书脊、反光、倾斜、遮挡和竖排文字的效果，因为这些场景最容易造成漏检或识别错误。

## 第十三步：导出 ONNX 和本地部署

YOLO 模型可以导出为 ONNX：

```bash
yolo export model=runs/book\\\_spine/yolo\\\_spine\\\_seg/weights/best.pt format=onnx imgsz=1280
```

部署方式可以选择：

* Python 命令行程序：适合离线批处理；
* FastAPI 服务：适合其他系统调用；
* PySide6 桌面程序：适合人工查看和修正；
* ONNX Runtime：适合减少部署环境对 PyTorch 的依赖。

FastAPI 接口的基本形式：

```python
from fastapi import FastAPI, UploadFile, File

app = FastAPI()

@app.post("/recognize")
async def recognize(file: UploadFile = File(...)):
    content = await file.read()
    with open("input.jpg", "wb") as output:
        output.write(content)

    result = process\\\_image("input.jpg")
    return result
```

启动服务：

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## 第十四步：常见问题处理

|问题|处理方法|
|-|-|
|相邻书脊被合并|增加密集排列标注，提高 `imgsz`，补充困难样本|
|窄书脊漏检|使用更大模型，提高原图分辨率，补充窄目标数据|
|文字方向错误|四方向 OCR，比较候选结果置信度|
|书名不完整|裁剪时扩边，检查透视四边形，降低 OCR 检测阈值|
|反光导致乱码|拍摄时减少反光，并尝试 CLAHE、灰度和锐化|
|结果顺序混乱|根据中心点坐标排序并进行分行聚类|
|CPU 速度较慢|使用 YOLO-n/s、ONNX Runtime 和批量推理|
|PaddleOCR 接口报错|根据当前 PaddleOCR 版本调整初始化参数和结果解析代码|

## 推荐的最小可行版本

第一版可以只实现以下内容：

1. 安装 Ultralytics、OpenCV、PaddleOCR 和 PaddlePaddle。
2. 标注一个 `spine` 类别。
3. 训练 `yolo11s-seg.pt`。
4. 使用掩码裁剪每本书的书脊。
5. 对裁剪图执行四方向 OCR。
6. 输出文字、置信度和裁剪图片路径。

完成最小版本后，再增加多版本图像增强、书名词典匹配、低置信度复核界面和 ONNX 部署。

## 最终推荐配置

```text
分割模型：YOLO11s-seg
分割输入尺寸：1280
图像处理：OpenCV 掩码裁剪 + 透视矫正 + 2 倍放大 + CLAHE
OCR：PaddleOCR 中文模型
方向策略：四方向 OCR，按置信度选优
后处理：字符清洗 + 置信度分级 + 本地图书词典匹配
部署：Python + FastAPI 或 ONNX Runtime
```

该方案的模型、图片和推理过程都可以放在本地，适合对数据隐私、离线运行和后续定制有要求的场景。最终识别效果主要取决于书脊标注质量、原始图片中文字分辨率，以及透视和方向处理是否准确。

## 已准备的数据集（2026-10-08）

已下载并转换 wenrenchuyu/book-spine-dataset：442 张图片、11,750 个书脊分割实例。训练/验证/测试为 353/44/45 张，data.yaml 已配置。详细目录、清洗记录与复核方法见 [数据集处理说明](dataset_preparation.md)。模型已完成 100 轮 YOLO11n-seg 训练，最终独立测试集分割 mAP50 为 0.992、mAP50-95 为 0.733。使用 `scripts/detect_and_crop_spines.py` 处理测试集后生成 1,278 个书脊裁剪结果，见 `crops/detected_test/`。
