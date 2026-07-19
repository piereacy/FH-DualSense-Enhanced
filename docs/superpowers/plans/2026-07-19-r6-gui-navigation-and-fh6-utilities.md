# Enhanced R6 GUI 导航与 FH6 实用功能实施计划

日期：2026-07-19  
状态：待实施  
对应规格：`docs/superpowers/specs/2026-07-19-r6-gui-navigation-and-fh6-utilities-design.md`

## 1. 固定基线与定向回归入口

- 保留当前 R6 未提交工作树，不执行 `reset`、`stash` 或整文件覆盖。
- 记录 `git status --short --branch`、最近提交和本轮涉及文件。
- 先运行现有 GUI 总览、System 初始化、配置默认值和翻译契约测试，区分既有问题与本轮回归。
- 修改 README 或提交/推送前先 `git fetch origin`，对比远端三语 README 并进行语义合并。

## 2. 将 GUI 页面改成一次挂载与 `tkraise()` 切换

- 在 `src/modules/gui/main.py` 中让全部 tab frame 只 `grid()` 一次，并共享同一内容单元格。
- 改写 `_select_nav()`：不再执行 `pack_forget()` 或重复 `pack()`，仅更新导航按钮、调用旧页 `on_hide()`、执行目标页 `tkraise()`，再调用新页 `on_show()`。
- 对非法页面键或切换异常保留当前页面并记录错误，不能让导航进入半切换状态。
- 检查 `WheelRouter` 对重叠页面的命中规则，确保滚轮只送给当前 raised 页面。
- 新增纯单元测试，验证页面只挂载一次、切换不重建控件、生命周期钩子顺序及滚轮路由。

## 3. 稳定总览快速启动入口

- 将 Steam 安装发现重试间隔从 5 秒改为 30 秒，只扫描当前选中的 FH4/FH5/FH6。
- 为每个游戏保存 path hint、首轮结果、已验证安装、最近完成时间和 worker serial。
- 找到有效路径后停止周期发现；未找到时继续后台重试，但首轮之后不再把按钮切回“正在查找”。
- 路径设置变化、已知路径失效或显式重新验证时，使旧缓存失效并立即开始新 worker；丢弃旧 serial 结果。
- Xbox App 模式不运行 Steam 路径发现，AUMID 仍只在用户点击启动时查找。
- 将启动按钮、游戏选择器、平台选择器和 XInput action 状态组成 presentation tuple；只有 tuple 真正变化时才调用 `configure()`、`grid()` 或 `grid_forget()`。
- 新增 fake clock/worker 测试，覆盖找到后停止、30 秒静默重试、切换游戏只扫描当前代、path hint 失效和无变化不渲染。

## 4. 抽取 GUI `FH6 实用功能` 页面

- 新建 `src/modules/gui/fh6_utilities_tab.py`，迁移 `SystemTab` 中 FH6 中文文字加英文语音与 DualSense/PlayStation 图标两张卡片及其状态字段、worker 和操作回调。
- 业务调用继续复用 `modules/forzahorizon/fh6_language.py` 与 `controller_icons.py`，不复制文件事务实现。
- 给新页实现 `on_show()`/`on_hide()`：首次显示、路径变化、显式操作完成时扫描；未找到且页面可见时每 30 秒静默重试；找到后停止路径发现。
- 保留轻量进程检测以更新“请关闭 FH6”，并使用状态差异更新控件。
- 从 `src/modules/gui/system_tab.py` 完整移除两张卡、相关 timer、worker、字段和重复入口，只保留控制器、更新及应用级设置。
- 在 GUI 导航中把新页放在“系统与更新”之后、“语言”之前。

## 5. 同步 TUI 页面边界

- 新建 `src/modules/tui/fh6_utilities_tab.py`，把现有 FH6 语言与图标区块、worker 和操作处理从 `SystemTab` 移入。
- 在 `src/modules/tui/main.py` 注册同名独立 tab，并保持与 GUI 相同的导航顺序和能力边界。
- TUI `SystemTab` 不保留隐藏入口或重复 action；新页继续使用 Textual 的 `on_show()`/worker group 生命周期。
- 添加 TUI 组合/契约测试，验证两项工具只存在于新页。

## 6. 翻译与默认平台契约

- 在 English fallback 及 `src/lang/de.py`、`ja.py`、`ru.py`、`tr.py`、`zh.py`、`zh_tw.py` 中增加 `FH6 utilities` 页面和说明键；简体中文固定显示 `FH6 实用功能`。
- 核对 `Settings.preferred_forza_platform`、非法值归一化、恢复出厂和首次启动均回到 `steam`。
- 新增导航、翻译和默认平台测试；确保本地 `packaging/windows/dist/data/user_preferences.json` 不进入构建或 Release。

## 7. 同步用户文档与长期文档

- 在修改 README 前再次 fetch 并审阅远端；只调整三语 README 中两项 FH6 工具的入口位置，不加入内部探测算法或小设置说明。
- 更新老三样：`AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`，记录一次挂载导航、差异渲染、当前游戏单路发现和 `FH6 实用功能` 模块边界。
- 单独更新 `docs/PROJECT_STATE.md`，写明实现状态、测试、构建和仍待真实硬件/游戏验证项。
- 更新 R6 中英文 Release 正文，保持 Enhanced R6 命名和已有第三方鸣谢。

## 8. 完整验证与 Windows 构建

- 运行新增定向测试，再运行 `uv run --project src pytest -q`。
- 运行 `python -m compileall -q src/modules src/lang`、`git diff --check` 和项目现有文档/打包契约测试。
- 确认旧 frozen EXE 已退出后执行 `packaging\windows\build_exe.bat`。
- 用 `packaging/windows/write_sha256.py --check` 复核 sidecar，并验证 PE 版本、MZ 头、内置 FH6 MOD/ViGEm 资产哈希及 one-file 产物名称。
- 冻结环境首次启动使用干净数据目录，确认平台显示 Steam、页面切换无明显卡顿、快速入口不抖动、两项 FH6 工具只在新页出现。
- 记录最终 EXE 精确字节数、MiB、相对 R5 的增量与百分比；若超过 52 MiB 或现有第三方体积门槛，停止发布并重新取得用户确认。

## 9. 提交与发布边界

- 本轮仍属于 Enhanced R6，不创建 R7 版本号。
- 提交前按功能审阅 diff，避免把 `dist/data`、临时备份、运行日志或本机路径写入提交。
- 推送前再次 fetch 并确认远端没有新的 README/Release 输入；随后提交 R6 实现、推送 `main`，创建或更新 R6 Release，并上传 EXE 与匹配的 `.sha256`。
- Release 正文继续提供完整中文和英文说明；未真实验证的 Xbox App 游戏行为必须明确写“待确认”。
