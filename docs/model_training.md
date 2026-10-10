# 书脊分割模型训练

## 当前训练

- 模型：预训练 YOLO11n-seg，单类别 `spine`。
- 设备：NVIDIA GeForce RTX 5060 Laptop GPU，CUDA 13.0，AMP 已通过检查。
- 配置：1024 输入尺寸，batch=2，最多 100 轮，验证集早停 patience=20，随机种子 42。
- 当前后台进程从检查点第 20 轮继续训练。检查点、曲线、验证预测和指标保存在 `outputs/training/book-spine-yolo11n-seg-20261008/`。
- 后台日志：`outputs/training/training.log` 和 `outputs/training/training-error.log`。
- 当前检查点：`outputs/training/book-spine-yolo11n-seg-20261008/weights/last.pt`；最佳权重：`outputs/training/book-spine-yolo11n-seg-20261008/weights/best.pt`。
- 预训练权重：`weights/yolo11n-seg.pt`。

训练集 353 张、验证集 44 张；测试集 45 张留给最终独立评估。训练结束后用 `best.pt` 在测试集评估，再决定是否继续调参。

## 启动或断点续训

PowerShell 项目根目录运行：

```powershell
.\dependencies\venv\Scripts\python.exe .\scripts\train_book_spine.py
```

有最近检查点时脚本默认续训；没有检查点时从 `weights/yolo11n-seg.pt` 开始。日志和权重都写在项目目录内。若后台训练仍在运行，不要再启动第二个进程写入同一训练目录。
