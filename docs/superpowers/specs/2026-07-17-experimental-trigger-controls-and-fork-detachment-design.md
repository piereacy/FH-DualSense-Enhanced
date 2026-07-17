# 实验性扳机反馈收纳与仓库独立化设计

## 目标

先把 Enhanced R4 新增且默认关闭的实验性扳机反馈从普通“驾驶反馈”页面移入折叠的“实验性功能”，降低用户误开的概率；完成代码、测试和提交后，再将 `piereacy/FH-DualSense-Enhanced` 从上游 fork network 中独立出来，同时继续履行原项目许可证和第三方归属要求。

这两个阶段严格串行：实验性界面迁移完成并验证后，才允许执行不可逆的 GitHub 仓库独立化操作。

## 实验性功能边界

本轮只迁移下列 Enhanced R4 实验性扳机反馈：

- 涡轮增压阻力：`enable_boost_resistance` 及阈值、额外阻力参数。
- G 力阻力：`enable_gforce_resistance` 及强度、横向/纵向权重、满量程和 attack/release 参数。
- 碰撞扳机冲击：`enable_collision_trigger_l2`、`enable_collision_trigger_r2` 及频率、强度、持续时间参数。
- 松开扳机键时的路面纹理：`enable_trigger_surface_l2`、`enable_trigger_surface_r2` 及普通路面和减速带的频率、强度参数。

以下成熟功能不迁移：抓地力反馈、GT7 风格 ABS 墙、刹车/油门基础阻力、R2 扳机键红线反馈和握把红线反馈。灯条与 Player LEDs 不属于扳机反馈，也不在本轮迁移范围。

## GUI 与 TUI 设计

- 从 `src/modules/gui/controls_tab.py` 和 `src/modules/tui/controls_tab.py` 的普通 L2/R2 卡片中移除六个实验性开关。
- 将六个开关及其全部基础、进阶参数统一放入 `EXPERIMENTAL_SECTIONS`，由 GUI 与 TUI 共用相同分组顺序。
- 折叠区继续默认关闭，并保留“不建议自行调节”的提示。用户主动展开后仍可启用和调节，不额外增加二次确认弹窗。
- 建议分成三个用户可理解的区块：实验性动态阻力、实验性碰撞扳机反馈、实验性路面扳机反馈。G 力进阶参数并入动态阻力区，不再留下独立的重复卡片。
- 设置仍即时保存并即时推送到运行中的手柄；迁移只改变入口位置，不改变配置字段、Profile 格式、默认值或运行算法。
- 六个开关继续默认 `False`，恢复出厂设置后也保持关闭。已在命名 Profile 中明确启用的值不得被迁移过程覆盖。

## 验证

- 更新 GUI/TUI 分组契约测试，确认普通驾驶反馈页面不再包含六个实验性开关。
- 确认 GUI 与 TUI 的实验性折叠区均包含对应开关和参数，并默认折叠。
- 确认社区默认值 fixture 中六个开关仍为 `false`。
- 运行相关配置、GUI/TUI 和 Forza effects 定向测试，再运行全量 `pytest`、`compileall` 和 `git diff --check`。
- 本轮不改变扳机算法，因此不要求新的真实驾驶手感验证；若打包 EXE，则只做界面入口、折叠状态和配置保存冒烟测试。

## GitHub 仓库独立化

独立化使用 GitHub 官方的 `Settings -> General -> Danger Zone -> Leave fork network`，不采用删除仓库后重建的手工方案。执行前必须：

1. 建立包含所有 refs、branches 和 tags 的本地 mirror 备份。
2. 导出 R1、R2、R2 Preview、R3 的 Release 标题、正文、标签与资产，并下载所有 Release 资产。
3. 记录默认分支、仓库描述、Topics、Actions 配置、当前 stars、Issues、Pull Requests 和其他可见元数据。
4. 确认仓库仍为公开、体积小于 1 GB 且没有子 fork，满足 GitHub 的 Leave fork network 条件。

GitHub 明确说明脱离 fork network 是永久操作，不能重新接回原网络，而且仓库元数据可能丢失。用户已经明确授权在实现完成后执行，但仍以备份成功作为执行条件；任何备份失败都必须停止独立化。

## 独立化后的约束与检查

- 仓库名称和目标 URL 继续使用 `piereacy/FH-DualSense-Enhanced`；内置更新器、Release workflow 和 README 链接不应改向其他仓库。
- 本地保留 `upstream` remote，继续用于查阅原项目历史，但不把独立仓库重新接入 fork network。
- 验证 GitHub API 返回 `isFork: false`，默认分支、代码、tags、Release、资产和 Actions 状态可用；若 GitHub 未保留 Release，则用备份立即恢复。
- 普通仓库搜索的重新索引可能延迟，不把立即出现在搜索结果中作为操作成功的唯一标准。
- `LICENSE`、应用“关于与许可证”中的原作者署名、原项目链接和 Sponsor 链接必须继续保留；README 继续说明本项目是基于上游 1.6.2 的独立非官方衍生版本。
- `docs/THIRD_PARTY_NOTICES.md` 中 HorizonHaptics、DS5Dongle、vDS 等第三方归属不因仓库独立化而改变。
- 独立化不改变自定义许可证的个人、非商业限制，也不能把项目宣传为 OSI 开源项目或原作者认可的官方版本。

## 文档同步

- 实验性入口迁移属于当前开发状态变化，完成实现和验证后更新 `docs/PROJECT_STATE.md`。
- 仓库从 fork network 独立属于长期工作流和发布边界变化，执行成功后检查并同步“老三样”：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`。
- README 只需要保持功能、来源和许可证事实准确，不加入具体控件移动或 GitHub 管理操作的流水账。
