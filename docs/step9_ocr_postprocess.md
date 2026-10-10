# 第九步：清洗、排序和过滤 OCR 结果

第九步使用本地 OCR 已生成的 `ocr_results.json`，不重新识别，也不覆盖原始结果。脚本会清洗无效字符、重新计算质量等级、关联书脊检测坐标、按原图书架顺序排序，并生成低置信度人工复核队列。

## 运行完整测试集

在项目根目录执行：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\postprocess_ocr_results.py
```

默认输入是本地 RapidOCR GPU 的全量结果：

```text
outputs\ocr_rapid_gpu_test\ocr_results.json
```

如果 OCR 使用其他目录，只需要替换输入参数：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\postprocess_ocr_results.py `
  --ocr .\outputs\ocr_test\ocr_results.json `
  --output .\outputs\ocr_postprocessed_paddle
```

## 输出文件

结果写入 `outputs\ocr_postprocessed`：

| 文件 | 用途 |
|---|---|
| `ocr_postprocessed.json` | 按原图和书架顺序组织的全量结构化结果 |
| `books_by_image.json` | 第十步使用的按图片分组结果 |
| `ocr_postprocessed.csv` | 可在表格软件中筛选和核验的全量结果 |
| `review_queue.csv` | 仅包含空文本、低置信度、方向歧义或检测较弱的记录 |
| `summary.json` | 总数、质量分级、错误数和复核数量 |

每条结果保留 `text`、`confidence`、`quality`、`direction`、`source_image`、`book_id`、`row`、`column`、`bbox_xyxy` 和裁剪图路径。`row` 和 `column` 是原图中的阅读顺序，不是 OCR 检测框内部的文字顺序。

默认分级规则：

```text
high：confidence >= 0.80
medium：0.55 <= confidence < 0.80
low：confidence < 0.55
```

`review_queue.csv` 默认收录置信度低于 `0.55` 的结果，也会收录空文本、少于两个字符或四方向分数接近的结果，供人工检查。

## 调整阈值

例如将低于 `0.70` 的结果全部列入人工复核：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\postprocess_ocr_results.py `
  --review-threshold 0.70
```

原始 `outputs\ocr_rapid_gpu_test\ocr_results.json` 始终保持不变，后续可以反复调整阈值并重新生成后处理结果。
