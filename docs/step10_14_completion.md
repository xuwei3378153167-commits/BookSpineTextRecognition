# 第十步至第十四步：结构化结果、完整推理、评估与部署

## 第十步：结构化结果

第九步运行后会生成 `outputs/ocr_postprocessed/books_by_image.json`。该文件按原图分组，每张图包含按书架阅读顺序排列的 `books`，每本书保留文字、置信度、方向、检测框、裁剪路径和复核标记。

## 第十一步：完整本地推理

处理一张图片：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\run_book_spine_pipeline.py `
  --source .\input\shelf_001.jpg
```

处理目录：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\run_book_spine_pipeline.py `
  --source .\input
```

默认流程为 YOLO 分割、掩码裁剪、透视矫正、CLAHE 增强、RapidOCR GPU 四方向识别和第九步后处理。每次运行写入 `outputs/pipeline_runs/run-*/`，不会覆盖既有结果。

没有可用 CUDA 时可切换 PaddleOCR CPU：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\run_book_spine_pipeline.py `
  --source .\input\shelf_001.jpg --ocr-engine paddle-cpu
```

## 第十二步：测试与评估

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\evaluate_pipeline.py
```

评估报告写入 `outputs/evaluation/evaluation_report.json`。它包含测试集规模、检测数量、预处理失败数、OCR 质量分布、训练最终指标和独立 YOLO 测试指标。由于当前数据集没有逐本书名真值，报告不会虚构 OCR 字符准确率；`review_queue.csv` 是后续人工核验入口。

## 第十三步：ONNX 与本地 API

导出脚本：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\export_yolo_onnx.py
```

启动本地接口：

```powershell
.\dependencies\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

健康检查地址为 `http://127.0.0.1:8000/health`，识别接口为 `POST http://127.0.0.1:8000/recognize`。接口默认使用本地 RapidOCR GPU；可通过环境变量 `BOOK_SPINE_OCR_ENGINE=paddle-cpu` 切换 CPU OCR。

## 第十四步：运行验收

验收标准：

* `books_by_image.json` 能被 JSON 解析并包含书脊结果；
* 完整流水线的每个阶段都在同一运行目录落盘；
* `evaluation_report.json` 中预处理失败数为 0；
* `/health` 返回 `status: ok`；
* 原始权重、原始 OCR JSON 和测试数据不被覆盖。
