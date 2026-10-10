# Contributing

感谢参与 Book Spine OCR 项目。项目面向 Windows 本地运行，提交前请保持改动可复现，并避免把个人数据或本地运行产物推送到仓库。

## 工作流程

1. 从 `main` 更新本地代码：

   ```powershell
   git switch main
   git pull --ff-only origin main
   ```

2. 为每项功能或修复创建独立分支：

   ```powershell
   git switch -c feat/short-description
   ```

3. 完成修改后运行与改动相关的检查，并提交清晰的 commit。

4. 推送分支并创建 Pull Request，说明改动内容、测试命令和已知限制。

## 提交约定

推荐使用简短的 Conventional Commits 风格前缀：

- `feat:` 新功能
- `fix:` 修复问题
- `docs:` 文档修改
- `refactor:` 不改变行为的重构
- `chore:` 构建或维护修改

## 本地文件边界

以下内容不应提交：

- `dataset/`：从数据集仓库单独下载
- `dependencies/`：项目本地虚拟环境、缓存和模型依赖
- `weights/`：本地模型权重
- `crops/`、`outputs/`：裁剪图、OCR 结果和评估产物
- API Key、`config/*.env`、`.env` 及其他凭据

这些路径已写入根目录 `.gitignore`。如果误将大文件加入暂存区，请先执行：

```powershell
git status --short
git restore --staged path/to/file
```

## Pull Request 检查清单

- README 或相关文档已同步更新。
- 没有提交数据集、权重、密钥或生成文件。
- 运行了与改动相关的命令，并记录了结果。
- 对模型、OCR 或数据处理流程的行为变化给出了示例或说明。
