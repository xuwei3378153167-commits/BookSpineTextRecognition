# PaddleOCR-VL 1.6 本地识别

模型：`PaddlePaddle/PaddleOCR-VL-1.6`，官方权重版本 `c5630abae1d940eafe0697512a0325494b02ab42`，Apache-2.0。

本项目使用官方提供的 Transformers 推理方式，适合书脊、艺术字局部图像和普通图片 OCR；也提供 spotting、表格、公式、图表及印章任务。此入口输出模型生成的文本，不提供经过校准的字符置信度。它没有包含 PaddleOCRVL 完整流水线的自动版面分块和多页 PDF 解析。

## 安装

在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_paddlevl16.ps1
```

复用项目内 `dependencies\venv` 的 CUDA 13 PyTorch，安装 `transformers==5.20.1`、`accelerate==1.15.0`。模型和下载元数据保存在 `weights\PaddleOCR-VL-1.6`，依赖缓存保存在 `dependencies`。下载脚本需要网络；识别脚本强制只读取本地模型，图片不会上传。

## 运行

识别单张图片：

```powershell
.\scripts\run_paddlevl16.bat --input "你的图片.jpg"
```

识别已有的艺术字书脊样例：

```powershell
.\scripts\run_paddlevl16.bat --input crops/detected_test/004/spine_003_raw.jpg --output outputs/paddlevl16_smoke
```

批量识别目录：

```powershell
.\scripts\run_paddlevl16.bat --input crops/detected_test/004 --output outputs/paddlevl16_batch
```

相对输入、输出和模型路径均相对于项目根目录解析，可以从其他工作目录调用脚本。输出为 `ocr_results.json` 与便于 Windows 编辑器查看的 `ocr_results.txt`。重复运行会跳过相同图片、任务及旋转参数的成功记录；使用 `--overwrite` 可重新生成，输入图片被修改后也需要使用此选项。逐张写入结果，错误记录会保留并返回非零退出码。

可选参数：`--rotate 90`（逆时针旋转）、`--task spotting`（文字定位及识别）、`--max-images 5`、`--max-new-tokens 1024`、`--device cpu`。默认设备为 `cuda:0`，使用 BF16 和 PyTorch SDPA。`hit_token_limit=true` 表示输出可能被截断，需要增加生成长度。

艺术字、模糊字与书名需要人工核对；实际运行成功仅证明模型可用，不等于已经完成准确率评估。WinUI 窗口已添加 `PaddleOCR-VL 1.6 GPU` 引擎，选择后使用本地权重识别矫正后的彩色书脊图。该模型不提供现有评分规则所需的置信度，因此显示“未提供”和“待核验”，平均置信度显示破折号。

官方说明：https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6

## 本机部署验证（2026-10-18）

已接入 `run_book_spine_pipeline.py --ocr-engine paddlevl16-gpu`，并重新发布 WinUI 窗口。命令行全流程结果位于 `outputs/paddlevl16_validation/integration`。随后通过窗口选择新引擎，导入同一书脊样例并点击“开始识别”，实际完成全流程，用时约 18.2 秒；检测到主书脊与边缘局部共 2 个候选，主书脊识别非空、边缘局部为空。未知置信度与“待核验”标签正常显示。模型只加载一次，按书脊逐张推理，后处理保留检测坐标和书架顺序。

RTX 5060 Laptop 8GB；Python 3.13.7；PyTorch 2.14.1+cu130；Transformers 5.20.1；Accelerate 1.15.0。权重 1,917,255,968 字节，SHA256 为 `85a479d506a11e724e7285d395c551be69f41dbc16b6342d3cacfb189aed71db`，已与官方文件元数据核对一致。

使用 `crops/detected_test/004/spine_003_raw.jpg` 进行真实 GPU 推理，正常退出并写入 `outputs/paddlevl16_smoke/ocr_results.json`。模型加载约 2.88 秒，单图推理及处理约 3.42 秒，PyTorch 峰值分配显存约 1854.8 MiB（不包含其他程序及驱动占用）。识别得到：

```text
王超等来
名人名言录
上海
H033
19
```

艺术字主标题“名人名言录”识别正确，顶部细小的编者文字存在误识别；这是一张部署验收样例，不能推导总体准确率。运行期间禁用在线模型访问，使用本地权重。Transformers 对上游配置会输出 rope 字段和处理器弃用提示，当前样例已正常完成；没有修改官方权重或模型配置。
