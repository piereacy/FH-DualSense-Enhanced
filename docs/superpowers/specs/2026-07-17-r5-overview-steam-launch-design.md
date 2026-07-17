# Enhanced R5 总览 Steam 启动 FH6 设计

## 目标

在 GUI 总览的“快速入口”增加一个显式“启动 FH6”按钮。按钮复用现有 Windows Steam FH6 安装发现和精确进程检测，通过 Steam App ID `2483190` 启动游戏，并清楚区分正在查找、可以启动、正在启动、游戏运行中和未找到游戏。

本功能属于尚未发布的 Enhanced R5。完成实现、测试、冻结构建和可见 GUI 验收后，完整 R5 工作树提交并推送到 `main`，再通过现有 `workflow_dispatch channel=stable` 发布 R5。

## 已确认的产品决策

- 启动方式固定为 Steam URI `steam://run/2483190`，不直接执行 `ForzaHorizon6.exe`。
- 已检测到 FH6 运行时，按钮禁用并显示“FH6 运行中”，不重复唤起 Steam。
- 按钮放在总览“快速入口”卡片底部，横跨现有两列。
- 启动必须来自用户点击，不在应用启动、页面刷新或发现安装目录时自动启动游戏。
- 该按钮只启动游戏，不交换语言包、不修改 Steam 设置、不修改游戏设置。
- 保持现有单一青绿色 GUI，不增加界面变体。

## 方案选择

### 采用方案：总览独立复用现有 FH6 发现逻辑

总览拥有轻量的异步发现和启动状态，调用 `discover_fh6_install()`、`is_fh6_running()` 和新的 Steam 启动帮助函数。系统页现有语言包扫描与按钮逻辑保持独立，不在发布前重构成全局 FH6 状态服务。

该方案比无条件打开 Steam URI 更可信，因为只有确认本机存在有效的 Windows Steam FH6 安装后才启用按钮；同时比引入全局共享服务改动更小，不扩大 R5 发布风险。

### 未采用方案

- 无条件打开 Steam URI：实现最少，但没有安装发现和状态反馈，无法兑现“已获得游戏目录”的前提。
- 重构全局 FH6 状态服务：长期边界更统一，但会同时改写总览、系统页和应用生命周期，超出本次按钮功能的必要范围。

## 启动后端

`src/modules/forzahorizon/fh6_language.py` 增加可独立测试的 `launch_fh6_via_steam(install)`：

1. 要求当前平台是 Windows。
2. 使用 `validate_game_root()` 重新验证传入安装目录，避免使用已经失效的缓存。
3. 使用精确 `ForzaHorizon6.exe` 进程检测再次确认游戏没有运行。
4. 调用 Windows URI handler 打开 `steam://run/2483190`，不使用 shell 命令，也不直接启动游戏 EXE。
5. URI handler 缺失或操作系统提交 URI 失败时，抛出 `FH6LanguageError` 并保留原始原因供日志记录。URI 已被系统接受后，应用不声称能够判断 Steam 内部是否拒绝请求。

帮助函数不读取或修改 `CHS.zip`、`EN.zip`、临时交换文件或 Steam manifest 内容。安装发现只证明有效游戏根目录存在；语言包是否处于原始、交换或恢复状态不影响启动游戏。

## 总览状态和布局

`OverviewTab` 在现有四个快捷入口下方增加一个横跨两列的按钮。按钮状态如下：

| 状态 | 文案 | 是否可点击 |
| --- | --- | --- |
| 首次发现或重新发现 | 正在查找 FH6… | 否 |
| 有效安装且游戏未运行 | 启动 FH6 | 是 |
| 已提交 Steam URI，等待进程出现 | 正在启动 FH6… | 否 |
| 检测到精确游戏进程 | FH6 运行中 | 否 |
| 非 Windows、未找到有效安装或缓存失效 | 未找到 FH6 | 否 |

发现流程在后台线程执行，Tk 控件只由主线程更新。总览首次创建后立即安排发现；之后由现有每秒状态 tick 检查以下条件：

- 精确 FH6 进程是否出现或消失。
- 缓存的 `fh6_install_path` 是否改变。
- 距离上次发现是否超过重试间隔。

目录发现最多每 5 秒发起一次，并且同一时间只允许一个发现线程。检测进程仍使用现有 `is_fh6_running()`，不新增宽松的进程名匹配。

## 点击和超时流程

1. 点击时立即把按钮切换到“正在启动 FH6…”并禁用，防止双击。
2. 后台调用 `launch_fh6_via_steam()`。
3. 系统接受 URI 后，通过现有 toast 显示“已向 Steam 发送 FH6 启动请求”。
4. 总览继续每秒检测精确游戏进程；检测成功后显示“FH6 运行中”。
5. 20 秒内没有检测到进程时，清除启动中状态并恢复“启动 FH6”，允许用户重试。超时只代表尚未检测到游戏，不声称 Steam 启动失败。
6. URI 调用抛错时立即恢复可点击状态，通过 toast 显示短错误，并把完整异常写入日志。

如果点击和后台执行之间安装目录失效、游戏已经启动或平台不再满足条件，后端重新验证负责拒绝请求，界面不得继续显示虚假的启动成功。

## 翻译和文档

- 英文源文案和 `de`、`ja`、`ru`、`tr`、`zh`、`zh_tw` 六个非英语 catalog 同步新增固定字符串。
- `.github/workflows/release.yml` 的 R5 中文与英文正文补充总览启动按钮、Steam App ID 启动方式和“游戏运行中禁用”的行为。
- `AGENTS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md` 按“老三样”约定检查并同步长期边界。
- `docs/PROJECT_STATE.md` 在实现、冻结构建和发布各阶段记录真实进度，不提前把 Release 写成成功。
- 用户 README 保持精简，不加入按钮状态机细节；必要设置继续要求 Steam Input 开启和游戏内振动关闭。

## 测试与验收

### 自动测试

- Windows 有效安装时使用精确 URI `steam://run/2483190`。
- 非 Windows、安装失效和游戏已运行时拒绝启动。
- 操作系统 URI handler 报错时转换为 `FH6LanguageError`。
- 总览源码契约确认使用异步发现、横跨两列按钮、启动中防双击、20 秒超时和现有每秒刷新入口。
- 翻译契约覆盖所有新增固定文案。
- Release 契约确认中文与英文正文都描述启动按钮。
- 现有语言包扫描、交换、还原和恢复测试必须继续通过，证明启动功能没有改变文件管理边界。

### 本地验收

- 运行相关定向测试和 `uv run --project src pytest -q`。
- 运行 `python -m compileall -q src/modules src/lang`、`uv lock --check --project src` 和 `git diff --check`。
- 启动源码 GUI，确认按钮初始状态、可点击状态和 FH6 已运行时的禁用状态。
- 重建 `FH-DualSense-Enhanced-R5.exe`，复核唯一规范资产、95-byte sidecar、SHA-256、MZ 头、R5 版本资源和 `--help`。
- 启动冻结 GUI，目视确认按钮布局和 Steam 启动请求。真实启动测试不得点击语言交换按钮；记录游戏内振动与 Steam Input 是否参与本轮触觉验证。

## 发布流程

1. 只在全部自动测试、冻结构建和 GUI 冒烟通过后提交完整 R5 工作树。
2. 明确检查工作树范围，保留用户已有的 R3/R4 扳机诊断文档，不静默丢弃或覆盖。
3. 推送 `main` 到 `origin`，目标仓库固定为 `piereacy/FH-DualSense-Enhanced`。
4. 使用 `gh workflow run release.yml --repo piereacy/FH-DualSense-Enhanced --ref main -f channel=stable` 触发稳定发布恢复入口。
5. 等待 `prepare`、`bundle`、`exe`、`elf` 和 `release` 全部成功。
6. 独立验证 R5 Release 为非 Draft、非 Prerelease，并核对规范 Windows EXE、`.sha256`、ZUV、启动器和 Linux ELF 资产。
7. 下载线上 EXE 与 sidecar，重新计算哈希并复核版本资源；失败时不移动或覆盖已发布 R1 至 R4。

## 非目标

- 不直接运行 `ForzaHorizon6.exe`。
- 不在 TUI 增加游戏启动按钮。
- 不自动关闭 Steam、游戏或本应用。
- 不在启动游戏前自动交换、修复或还原语言包。
- 不实现 Steam 下载进度、游戏启动日志、进程聚焦或停止游戏按钮。
- 不恢复 Stage、Studio 或其他界面变体。
