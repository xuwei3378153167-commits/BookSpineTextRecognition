# 本地书脊文字识别 · 桌面端

Windows 11 Fluent 风格的本地书脊识别工具。界面以米白 `#F7F5EF` 和陶土色 `#DA7756` 为主，保留现有 YOLO → 矫正增强 → OCR → 结果整理流程。

## 启动

双击本目录已有的 `BookSpineTextRecognition.exe.lnk`，或运行 `publish/BookSpineTextRecognition.exe`。请保留整个 `publish` 文件夹及其依赖文件。

## 使用

1. 点击“选择图片”，输入本地图片路径 / HTTP(S) 图片地址，或拖入一张图片。支持 JPG、PNG、BMP、WEBP，最大 50 MB。
2. 选择 RapidOCR GPU、PaddleOCR GPU 或 PaddleOCR CPU；“高级设置”中可配置 YOLO 设备，GPU 填 `0`，CPU 填 `cpu`。
3. 点击“开始识别”。底部五个圆形节点依次对应图片准备、书脊检测、矫正增强、文字识别、结果整理。真实阶段推进后，完成节点显示勾号，连线填充至最后一个完成节点；当前节点轻微呼吸，全部完成后保留。取消显示暂停，失败显示红叉。
4. 在“原图 / 检测结果”间切换；滚轮围绕鼠标位置缩放，按住中键自由平移，松开停止。双击图片或点击全屏图标打开全屏查看器，按 Esc / 点击退出按钮 / 再次双击图片返回。普通与全屏模式都支持缩放和平移；“适应”恢复整图居中。100% 表示当前适应窗口的基准比例。
5. 识别结果只有“顺序”和“置信度”两个排序按钮，重复点击当前按钮可切换升降序。顺序按数字序号排列，置信度使用未舍入的原始数值排序。
6. 结果可选中文字，点击每条右侧图标复制单条文字，或“复制全部”复制含表头的 TSV 表格，可粘贴到 Excel。复制顺序与当前显示顺序一致。

窄窗口自动改为上下布局；高度不足时页面可滚动。取消、清空、关闭会清理当前推理的临时文件，识别结果不自动存入历史记录。输入原图不会被修改。

## 图标

`BookSpineTextRecognition/Assets/BookSpine.svg` 是可编辑设计源；`BookSpine.png` 为 1024 × 1024 透明 PNG；`BookSpine.ico` 包含 16、20、24、32、40、48、64、128、256 像素帧。程序文件、窗口与现有快捷方式已使用此图标。

`tools/render_icon.cjs` 通过 Node.js + sharp 从 SVG 重建 PNG 和 ICO；可将 `NODE_PATH` 指向已有的 sharp 安装目录，无需改动识别依赖。

## 构建

在项目根目录运行 `scripts/publish_winui.ps1`；脚本优先使用项目内 `dependencies/dotnet-sdk/dotnet.exe`，输出到 `desktop/publish`。当前程序为 .NET 8 / WinUI 3 x64 自包含发布。

初次改版验收见 `validation/验收记录.md`；本次节点进度、全屏查看及排序更新见 `validation/interaction-update/验收记录.md`。

图片变换与排序的逻辑检查：在项目根目录运行 `dependencies/dotnet-sdk/dotnet.exe run --project desktop/tests/InteractionChecks/InteractionChecks.csproj -c Release`。
