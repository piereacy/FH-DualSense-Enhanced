# 实验性扳机反馈迁移、Enhanced R4 发布与仓库独立化计划

日期：2026-07-17

依据：`docs/superpowers/specs/2026-07-17-experimental-trigger-controls-and-fork-detachment-design.md`

## 目标

将 Enhanced R4 新增的六个实验性扳机开关及其全部参数收进默认折叠的实验性功能区域，完成 README 和项目状态同步、全量测试与 Windows R4 构建；然后备份 GitHub 仓库并使用官方 Leave fork network 取消 fork 关系，最后在独立的 `piereacy/FH-DualSense-Enhanced` 发布 Enhanced R4。

## 实施顺序

### 1. 先更新界面分组契约测试

修改：

- `tests/test_haptic_settings.py`
- 必要时扩展 `tests/gui/test_r4_frontend.py`

覆盖：

- GUI/TUI 普通驾驶反馈页不再包含六个实验性开关。
- GUI/TUI 的 `EXPERIMENTAL_SECTIONS` 包含涡轮、G 力、L2/R2 碰撞和 L2/R2 路面纹理开关及全部参数。
- 实验性区域继续默认折叠并显示警告。
- 社区默认 fixture 中六个开关继续为 `false`。

### 2. 迁移 GUI 与 TUI 控件

修改：

- `src/modules/gui/controls_tab.py`
- `src/modules/tui/controls_tab.py`
- `src/modules/gui/settings_tab.py`
- `src/modules/tui/settings_tab.py`
- 必要的 `src/lang/*.py`

实现：

- 普通 L2/R2 卡片只保留成熟反馈。
- 实验性折叠区按动态阻力、碰撞反馈和路面反馈分组。
- G 力进阶参数并入动态阻力组，消除重复卡片。
- 不改变字段名、默认值、Profile 序列化、即时保存或运行算法。

### 3. 更新三语 README 和项目文档

修改：

- `README.md`
- `docs/ReadmeZH.md`
- `docs/ReadmeJA.md`
- `docs/PROJECT_STATE.md`
- 按长期边界检查并更新 `AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`

内容：

- 三语 README 用四到六个用户可感知类别明确列出当前 Enhanced 相比上游 1.6.2 的累计增强。
- 不在 README 记录具体控件搬家；Release body 单独列 Enhanced R4 相比 Enhanced R3 的变化。
- 项目状态记录实验性入口迁移、验证、发布准备和仓库独立化状态。
- README 继续保留非官方衍生说明；应用内最低限度保留许可证要求的署名、原项目和 Sponsor 链接。

### 4. 代码验证

依次执行：

1. 分组、默认值、GUI/TUI 和 Forza effects 定向测试。
2. `uv run --project src pytest -q`。
3. `python -m compileall -q src/modules src/lang`。
4. `git diff --check`、完整 diff 和工作区检查。

本轮不改变触觉算法，真实 Forza 手感验证不是迁移的阻断项；游戏内振动与 Steam Input 记录为“未参与”。

### 5. 构建和冒烟 Enhanced R4

执行：

- `packaging\windows\build_exe.bat`
- 核对唯一 `FH-DualSense-Enhanced-R4.exe` 和同名 `.sha256`。
- 验证文件哈希、版本资源、内置 Update Helper 和许可证文件。
- 启动冻结 GUI，检查驾驶反馈页、实验性折叠区、滚轮、退出提示和系统更新入口。
- 确认没有 crash log、残留进程或误加入 Git 的构建产物。

### 6. 提交、整合并推送

- 将代码、测试和文档按可审计的提交落到 `feat/r4-ui-updater-haptics`。
- 把 `origin/main` 的两份已发布 README 提交与 R4 分支整合，解决等价提交可能产生的冲突。
- 在本地 `main` 创建明确的 R4 合并提交，重新运行关键验证后推送 `origin/main`。
- 不提前创建 `R4` tag，避免 Release workflow 在仓库仍属于 fork network 时启动发布。

### 7. 完整备份 GitHub

在工作区外的时间戳目录保存：

- `git clone --mirror` 得到的全部 refs、branches 和 tags。
- 仓库 REST/GraphQL 元数据 JSON。
- R1、R2、R2 Preview、R3 的 Release 元数据、正文和全部资产。
- Issues、Pull Requests、Actions runs、仓库描述和 Topics 的可导出记录。

逐项核对备份可读且资产非空；任何失败都停止独立化。

### 8. 取消 fork 关系

- 使用 GitHub `Settings -> General -> Danger Zone -> Leave fork network`。
- 不删除并重建仓库。
- 操作后验证 `piereacy/FH-DualSense-Enhanced` 仍可访问且 API 返回 `isFork: false`。
- 核对默认分支、tags、历史 Release、资产和 Actions；缺失的 Release 依据备份恢复。
- 保留本地 `upstream` remote，但不重新加入 fork network。

### 9. 发布 Enhanced R4

- 在独立仓库创建并推送稳定 tag `R4`，由 `.github/workflows/release.yml` 构建 ZUV、Windows EXE、Linux ELF 和 Release。
- Release body 必须含中文 R4 说明，并把实验性扳机功能标为默认关闭、位于实验性折叠区。
- 不在面向用户的 Release 文案中使用 “Miku Console” 产品概念。
- 等待 Actions 全部完成，核对规范 EXE、`.sha256`、ZUV、启动脚本、Linux ELF、`LICENSE` 和第三方声明。
- 验证内置更新器能够发现 R4；R3 到 R4 的实际替换若无法安全自动执行，明确记录为未执行。

### 10. 发布后收尾

- 更新 `docs/PROJECT_STATE.md` 的公开稳定版、Git 状态、构建结果、GitHub 独立状态和 Release URL。
- 仓库独立属于长期工作流变化，同步检查“老三样”。
- 提交并推送发布后文档；确认工作区干净、GitHub 默认分支正确、R4 标记为 Latest。
