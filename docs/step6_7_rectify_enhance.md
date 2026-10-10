# 第六、七步：透视矫正与图像增强

运行：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\rectify_and_enhance_spines.py `
  --manifest .\crops\detected\detections.json `
  --output .\crops\preprocessed
```

输入是第五步的 `detections.json`。脚本从每个书脊的分割多边形计算旋转矩形，做透视变换，并自动将横向结果旋转成竖直方向。然后按高度放大到约 1600 像素，在 LAB 亮度通道做 CLAHE 局部对比度增强，同时输出灰度图。

输出文件：

- `spine_001_rectified.jpg`：几何矫正后的彩色图；
- `spine_001_clahe.jpg`：建议给 OCR 使用的增强图；
- `spine_001_gray.jpg`：灰度备用图；
- `preprocess.json`：源文件、置信度、局部四角、输出尺寸和失败记录。

本次对独立测试集的 1,278 个检测实例全部处理成功，输出目录为 `crops/preprocessed_test/`。
