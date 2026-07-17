# README 中性命名与游戏振动警告设计

## 本轮目标

本轮只修改面向 GitHub 用户的三语 README，不修改 Enhanced R4 程序窗口、总览页、翻译目录、Release workflow 或 Windows 版本资源。应用内移除 “Miku Console” 及其他 R4 功能设计留到用户后续讨论。

## README 命名

- 根 `README.md`、`docs/ReadmeZH.md`、`docs/ReadmeJA.md` 的功能亮点不再使用 “Miku Console” 作为产品概念。
- 对应条目改为中性的“简洁桌面界面”，保留可选手柄灯效这一用户可感知能力。
- 项目名称仍为 `FH-DualSense-Enhanced`，不引入新的界面品牌或代号。

## 必须关闭游戏内振动

三种语言在“必需的游戏设置”中使用 GitHub `IMPORTANT` 提示，明确表达：

- 必须在 Forza 游戏设置中关闭“振动”，否则游戏原生 rumble 会争用、掩盖或干扰本项目的握把触觉，导致握把反馈无法正常工作。
- Steam Input 仍然必须开启；用户只关闭游戏内的“振动”选项，不关闭 Steam Input。
- 删除原来“可以保持开启，仅在比较时临时关闭”的建议性说法。

警告不展开菜单、CG 和过场振动的取舍，避免 README 再次变长。

## 测试和交付

- 文档契约检查三种 README 均不包含 “Miku Console”。
- 文档契约检查英文、简体中文和日语都同时包含“关闭游戏内振动”和“保持 Steam Input 开启”的强制含义。
- 三份 README 继续满足篇幅上限和相对链接检查。
- 在 R4 分支运行定向测试、全量 `pytest` 和 `git diff --check`。
- 生成独立 README 提交并移植到 GitHub 默认分支 `main`，不合并 R4 业务代码。
- 在 `main` 重新运行适用的文档测试和全量测试，再推送 `origin/main` 并通过 GitHub API 核对正文。

## 延后范围

以下内容本轮不修改，等待用户稍后讨论 Enhanced R4 功能设计：

- `src/modules/gui/main.py` 的窗口标题。
- `src/modules/gui/overview_tab.py` 及 `src/lang/` 的总览文案。
- `packaging/windows/fhds.spec` 的文件描述。
- `.github/workflows/release.yml` 的 R4 Release 正文。
- 技术文档中记录旧界面方案的历史决策。
