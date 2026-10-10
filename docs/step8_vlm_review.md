# 第八步：低置信度书脊的视觉模型复核

本地 GPU OCR 是默认流程。仅当本地结果为空或置信度低于 `0.55` 时，才将裁剪后的单个书脊图发送给第三方视觉模型复核。本批数据会筛选出 223 个候选，不会上传其余高置信度书脊，也不会上传整张书架原图。

复核脚本使用 OpenAI 兼容的 `POST /chat/completions` 协议，需要模型具备图片输入能力。它不依赖大模型完成书脊分割、裁剪或常规 OCR；云端模型只作为艺术字、反光、低对比和特殊排版的兜底。

## 运行

双击以下文件：

```text
scripts\run_low_confidence_vlm.bat
```

按提示输入：

1. Base URL，例如 `https://api.example.com/v1`；
2. 视觉模型名。可直接回车让脚本查询 `/models` 并挑选名称中含 `vision`、`vl`、`gpt-4o`、`gemini`、`claude` 或 `qwen` 的模型；
3. API Key。PowerShell 会以隐藏输入方式读取，仅在本次进程的环境变量中使用，不保存到项目文件。

如果服务商的模型列表无法表明哪个模型支持图片输入，请填写服务商文档中的准确视觉模型名。

先验证候选数量、且不上传图片：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\vlm_review_low_confidence.py --dry-run
```

命令行运行（API Key 仅作为当前 PowerShell 会话变量）：

```powershell
$env:VLM_BASE_URL = 'https://api.example.com/v1'
$env:VLM_MODEL = 'your-vision-model'
$env:VLM_API_KEY = Read-Host 'API Key'
.\dependencies\venv\Scripts\python.exe .\scripts\vlm_review_low_confidence.py
Remove-Item Env:VLM_API_KEY
```

## 输出与断点续跑

结果位于 `outputs\vlm_review_low_confidence`：

|文件|用途|
|-|-|
|`review_results.json`|每个复核样本的本地 OCR、视觉模型结果、模型名、时间和失败原因|
|`review_results.csv`|可在 Excel 查看的比对表|
|`ocr_results_merged.json`|保留所有 1,278 条记录；有非空复核文本时替换展示文本，同时保留 `local_ocr` 原始结果|
|`summary.json`|候选数、成功数和失败数|

每处理一张图就落盘；网络中断后再次运行同一命令会跳过已成功的记录。若个别图返回空文本，会保留本地 OCR 结果，并在复核表中显示空的视觉模型文本。

## 可调参数

提高阈值会扩大上传量，例如复核置信度低于 `0.70` 的样本：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\vlm_review_low_confidence.py --threshold 0.70
```

先试跑 5 张以确认 Base URL、模型和计费正常：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\vlm_review_low_confidence.py --max-images 5
```

视觉模型输出仍可能误读艺术字，因此应优先人工抽查 `review_results.csv` 中本地文本与复核文本差异较大的记录。
