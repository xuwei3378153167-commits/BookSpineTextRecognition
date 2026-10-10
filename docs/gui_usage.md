# 窗口识别程序

启动：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\book_spine_gui.py
```

在“图片地址”中填写本地图片路径，或者填写 `http://` / `https://` 图片地址。也可以点击“选择图片”打开文件选择器。

程序使用项目现有的 `run_book_spine_pipeline.py` 完成 YOLO 书脊分割、透视矫正和本地 OCR。结果区域显示每个书脊的文字、置信度、质量等级和方向，左侧显示带检测框的图片。

默认 OCR 引擎是 `rapid-gpu`，需要可用的 ONNX CUDA 环境。CPU 环境请选择 `paddle-cpu`；YOLO 检测设备也应填写为 `cpu`。

程序不会把输入图片、下载内容、裁剪图、增强图或 OCR JSON 写入项目目录。所有中间文件位于程序创建的临时目录，关闭窗口时自动删除。窗口运行期间也不提供保存结果的按钮。
