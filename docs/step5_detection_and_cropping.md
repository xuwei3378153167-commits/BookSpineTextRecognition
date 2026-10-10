# 第五步：检测书脊并生成裁剪图

训练完成后使用：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\detect_and_crop_spines.py `
  --source .\input `
  --weights .\outputs\training\book-spine-yolo11n-seg-20261008\weights\best.pt `
  --output .\crops\detected `
  --conf 0.35 --iou 0.50 --imgsz 1024 --device 0
```

脚本可以接收单张图片或图片目录。每张图片保存一张 `_detected.jpg` 可视化图，并为每个检测实例建立同名子目录。`spine_001.jpg` 是按分割掩码裁剪、掩码外区域置白的 OCR 输入图；`spine_001_raw.jpg` 是带书架背景的矩形原图裁剪，用于排查误检；`detections.json` 保存置信度、检测框、掩码多边形及文件路径。

本次使用最终 `best.pt` 处理独立测试集：45 张图片，生成 1,278 个书脊实例；共 1,278 张掩码裁剪、1,278 张原始矩形裁剪和 45 张检测可视化图。结果位于 `crops/detected_test/`，完整性检查显示 0 个缺失裁剪文件。

测试集评估结果（`outputs/training/book-spine-test-evaluation/`）：

| 指标 | 数值 |
| --- | ---: |
| Box Precision | 0.983 |
| Box Recall | 0.982 |
| Box mAP50 | 0.993 |
| Mask Precision | 0.982 |
| Mask Recall | 0.980 |
| Mask mAP50 | 0.992 |
| Mask mAP50-95 | 0.733 |

示例检测图：`crops/detected_test/004_detected.jpg`。示例书脊裁剪：`crops/detected_test/004/spine_001.jpg`。
