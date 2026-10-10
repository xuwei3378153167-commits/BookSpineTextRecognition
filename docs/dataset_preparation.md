# 书脊数据集准备

数据来源：https://github.com/wenrenchuyu/book-spine-dataset

下载日期：2026-10-08。下载时 main 指向 `9464960bb6e9ef4b88d2cc51ccecdc10b121c454`；实际归档 SHA-256 记录在处理报告中。

## 文件位置

- `dataset/raw/book-spine-dataset-main.zip`：下载的原始压缩包。
- `dataset/raw/book-spine-dataset-main/`：解压的原始图片、LabelMe JSON 和上游说明。
- `dataset/images/train/`、`val/`、`test/`：供 YOLO 使用的图片。
- `dataset/labels/train/`、`val/`、`test/`：同名 YOLO 分割标签。
- `data.yaml`：数据集配置，类别编号 0 为 `spine`。
- `scripts/prepare_book_spine_dataset.py`：可复现的转换脚本。
- `outputs/dataset_preparation/report.json`：图片划分、校验值、标注计数及问题记录。
- `outputs/dataset_preparation/annotation_preview.jpg`：抽样标注叠加预览。

## 处理方式

1. 解压并保留原始数据；校验解压文件的 CRC。
2. 解码每张图片，检查图片与 JSON 一一配对及尺寸一致性。
3. 将 `book` 类统一为 `spine`；多边形直接转换，旋转矩形保留四角，普通矩形展开为四角。矩形标注仅提供近似轮廓，不等于精细像素掩码。
4. 在图像边界裁切越界多边形；排除退化多边形，并在报告中记录。
5. 按解码后的 RGB 像素 SHA-256 去除完全重复图片，防止它们跨集合出现。
6. 使用随机种子 42，以约 80% / 10% / 10% 划分训练、验证、测试集，总量不超过 500 张。保留原始分辨率。
7. 检查所有生成标签的类别、坐标范围和点数，并生成可视化预览。

划分按图片随机进行；尚未按同一本书、同一书架或拍摄场景分组。后续应使用独立拍摄场景评价泛化效果。

## 运行方法

在项目根目录运行：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\prepare_book_spine_dataset.py
```

需要 Pillow；当前转换使用项目内虚拟环境。脚本发现输出目录已有图片或标签时会停止，以免混合或覆盖数据。正常使用已准备好的数据时无需再次运行。

本次只准备分割训练数据，没有开始训练。该数据集未提供书脊文字转录，不能直接用作 OCR 文本识别监督数据。上游未发现明确的数据许可证，保留来源说明，其他使用授权以作者说明为准。

## 本次处理结果

- 共 442 张：训练 353、验证 44、测试 45；最终 11,750 个书脊实例。
- 4 个异常类别名经图像核对确认为书脊；342.jpg 的两条轮廓指向同一书脊，保留第一条、移除第二条。
- 裁切 1 个越界轮廓；未发现完全相同的 RGB 图片。
- Ultralytics 校验自动重新保存了 238 张 JPEG，以修复文件尾格式；原始图片完整保留在 raw 中，尺寸未改变。原始像素哈希记录在 report.json。
- 最终全量校验：442 张、11,750 个实例、0 个错误。首次修复日志见 yolo_validation.json，最终结果见 yolo_validation_final.json。
- 可运行 scripts/validate_book_spine_dataset.py 复核；该校验会修复训练副本中的 JPEG 文件格式。
